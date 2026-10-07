import csv
import os
from typing import List

import openpyxl
from django.conf import settings
from django.db.models import Case, Prefetch, When
from django.http import HttpResponse
from django.utils import timezone
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

from sales.models import Order, OrderProduct


class OrderExportService:
    """
    Service responsible for querying and formatting orders into logistics/courier
    bulk upload export templates (Excel .xlsx and CSV .csv).
    """

    HEADERS: List[str] = [
        "ItemType",
        "StoreName",
        "MerchantOrderId",
        "RecipientName(*)",
        "RecipientPhone(*)",
        "RecipientCity(*)",
        "RecipientZone(*)",
        "RecipientArea",
        "RecipientAddress(*)",
        "AmountToCollect(*)",
        "ItemQuantity",
        "ItemWeight",
        "ItemDesc",
        "SpecialInstruction",
    ]

    TEMPLATE_PATH = os.path.join(settings.BASE_DIR, "merchant_bulk_order_sample.xlsx")

    STORE_NAMES: List[str] = [
        "Yachu Jorpati",
        "Yachu Gairidhara",
        "Yachu Kritipur",
        "Yachu Baliyo ventures Pvt.Ltd",
        "Yachu Bhaktapur",
        "Yachu Jhamsikhel",
        "New Uttam Traders",
        "Yachu Soalteemode",
        "Yachu Lagankhel",
        "Yachu Sitapaila",
        "Yachu Baneshwor",
    ]

    FRANCHISE_STORE_MAPPING = {
        "jorpati": "Yachu Jorpati",
        "gairidhara": "Yachu Gairidhara",
        "kritipur": "Yachu Kritipur",
        "chibe": "Yachu Baliyo ventures Pvt.Ltd",
        "sankhamul": "Yachu Baliyo ventures Pvt.Ltd",
        "bhaktapur": "Yachu Bhaktapur",
        "jhamsikhel": "Yachu Jhamsikhel",
        "swyambhu": "New Uttam Traders",
        "main": "New Uttam Traders",
        "soalteemode": "Yachu Soalteemode",
        "lagankhel": "Yachu Lagankhel",
        "sambridhi": "Yachu Sitapaila",
        "baneshwor": "Yachu Baneshwor",
    }

    @classmethod
    def match_store_name(cls, franchise) -> str:
        """
        Match an order's franchise to one of the predefined store names based on
        name or short_form, falling back to franchise.name.
        """
        if not franchise:
            return ""

        name = getattr(franchise, "name", "") or ""
        short_form = getattr(franchise, "short_form", "") or ""

        # 1. Exact case-insensitive match against STORE_NAMES
        for cand in [name, short_form]:
            cand_clean = cand.strip()
            if not cand_clean:
                continue
            for store in cls.STORE_NAMES:
                if cand_clean.lower() == store.lower():
                    return store

        # 2. Keyword/substring mapping
        for cand in [name, short_form]:
            cand_lower = cand.strip().lower()
            if not cand_lower:
                continue
            for key, store in cls.FRANCHISE_STORE_MAPPING.items():
                if key in cand_lower:
                    return store

        # 3. Fallback to franchise name
        return name.strip() if name else ""

    _cached_dropdown_cities: List[str] = []

    @classmethod
    def get_dropdown_cities(cls) -> List[str]:
        """
        Load and cache the list of city names from the template's Dropdown List sheet.
        """
        if cls._cached_dropdown_cities:
            return cls._cached_dropdown_cities

        if os.path.exists(cls.TEMPLATE_PATH):
            try:
                wb = openpyxl.load_workbook(cls.TEMPLATE_PATH, read_only=True)
                if "Dropdown List" in wb.sheetnames:
                    ws_dd = wb["Dropdown List"]
                    cities = []
                    for r in range(2, 350):
                        val = ws_dd.cell(row=r, column=3).value
                        if val:
                            cities.append(str(val).strip())
                    wb.close()
                    cls._cached_dropdown_cities = cities
            except Exception:
                pass
        return cls._cached_dropdown_cities

    @classmethod
    def match_city_name(cls, city_input: str) -> str:
        """
        Match an order's city against the official Pathao Dropdown List city_name column.
        """
        if not city_input:
            return ""
        c_in = str(city_input).strip().lower()
        if not c_in:
            return ""

        dropdown_cities = cls.get_dropdown_cities()
        if not dropdown_cities:
            return str(city_input).strip()

        # 1. Kathmandu Valley aliases
        if any(
            k in c_in for k in ["ktm", "kathmandu", "lalitpur", "bhaktapur", "patan"]
        ):
            for c in dropdown_cities:
                if "kathmandu valley" in c.lower():
                    return c
            return "Kathmandu Valley"

        # 2. Exact match
        for c in dropdown_cities:
            if c.lower() == c_in:
                return c

        # 3. Substring match
        for c in dropdown_cities:
            if c_in in c.lower():
                return c

        # 4. Word match without parentheses
        for c in dropdown_cities:
            cleaned_c = c.lower().replace("(", " ").replace(")", " ")
            if c_in in cleaned_c.split():
                return c

        return ""

    @classmethod
    def get_orders(cls, order_ids: List[int]):
        """
        Fetch orders by IDs using optimized queries to avoid N+1 query overhead.
        Preserves the order of incoming order_ids.
        """
        preserved_order = Case(*[
            When(pk=pk, then=pos) for pos, pk in enumerate(order_ids)
        ])

        return (
            Order.objects
            .filter(id__in=order_ids)
            .select_related("location", "franchise")
            .prefetch_related(
                Prefetch(
                    "order_products",
                    queryset=OrderProduct.objects.select_related("product__product"),
                )
            )
            .order_by(preserved_order)
        )

    @classmethod
    def prepare_order_row(
        cls, order: Order, weight: float = 1.0, store_name: str = ""
    ) -> list:
        """
        Transform an Order instance into the row format expected by the courier template:
        1. ItemType: "Parcel"
        2. StoreName: Matched from order.franchise against predefined store names
        3. MerchantOrderId: order.order_code or order.id
        4. RecipientName(*): order.full_name
        5. RecipientPhone(*): order.phone_number
        6. RecipientCity(*): "" (blank as requested)
        7. RecipientZone(*): "" (blank as requested)
        8. RecipientArea: order.location.name if order.location else (order.city or "")
        9. RecipientAddress(*): "" (blank as requested)
        10. AmountToCollect(*): COD Amount (total_amount - prepaid_amount)
        11. ItemQuantity: Total sum of item quantities in the order
        12. ItemWeight: Parcel weight (default 1.0)
        13. ItemDesc: Description of products (e.g., "1x Hair Oil, 2x Shampoo")
        14. SpecialInstruction: Remarks and/or landmark
        """
        # 1. ItemType
        item_type = "package"

        # 2. StoreName (use override if explicitly provided, else match from order.franchise)
        resolved_store = (
            store_name.strip() if store_name else cls.match_store_name(order.franchise)
        )

        # 3. MerchantOrderId
        merchant_order_id = order.order_code or str(order.id)

        # 4. RecipientName(*)
        recipient_name = order.full_name or ""

        # 5. RecipientPhone(*)
        recipient_phone = order.phone_number or ""

        # 6. RecipientCity(*) - matched from city_name in Dropdown List
        recipient_city = cls.match_city_name(order.city)

        # 7. RecipientZone(*) - blank as requested
        recipient_zone = ""

        # 8. RecipientArea
        recipient_area = order.location.name if order.location else (order.city or "")

        # 9. RecipientAddress(*) (delivery_address, city, and landmark if any)
        address_parts = []
        if order.delivery_address and order.delivery_address.strip():
            address_parts.append(order.delivery_address.strip())
        if order.city and order.city.strip():
            city_val = order.city.strip()
            if (
                not order.delivery_address
                or city_val.lower() not in order.delivery_address.lower()
            ):
                address_parts.append(city_val)
        if order.landmark and order.landmark.strip():
            landmark_val = order.landmark.strip()
            if (
                not order.delivery_address
                or landmark_val.lower() not in order.delivery_address.lower()
            ):
                address_parts.append(landmark_val)
        recipient_address = ", ".join(address_parts)

        # 10. AmountToCollect(*) (total_amount - prepaid_amount, non-negative)
        total = float(order.total_amount or 0)
        prepaid = float(order.prepaid_amount or 0)
        cod_val = max(0.0, total - prepaid)
        amount_to_collect = int(cod_val) if cod_val.is_integer() else round(cod_val, 2)

        # 11. ItemQuantity (sum of all product quantities)
        total_qty = sum(op.quantity for op in order.order_products.all())
        item_quantity = total_qty if total_qty > 0 else 1

        # 12. ItemWeight
        try:
            numeric_weight = float(weight)
            formatted_weight = (
                int(numeric_weight)
                if numeric_weight.is_integer()
                else round(numeric_weight, 2)
            )
        except (ValueError, TypeError):
            formatted_weight = 1

        # 13. ItemDesc
        product_items = []
        for op in order.order_products.all():
            try:
                p_name = op.product.product.name
            except AttributeError:
                p_name = "Product"
            product_items.append(f"{op.quantity}x {p_name}")
        item_desc = ", ".join(product_items)

        # 14. SpecialInstruction
        special_instruction = order.remarks.strip() if order.remarks else ""

        return [
            item_type,
            resolved_store,
            merchant_order_id,
            recipient_name,
            recipient_phone,
            recipient_city,
            recipient_zone,
            recipient_area,
            recipient_address,
            amount_to_collect,
            item_quantity,
            formatted_weight,
            item_desc,
            special_instruction,
        ]

    @classmethod
    def update_orders_logistics(
        cls, order_ids: List[int], logistics: str = "Pathao"
    ) -> None:
        """
        Update the logistics provider to 'Pathao' for the exported orders.
        """
        if order_ids:
            Order.objects.filter(id__in=order_ids).update(logistics=logistics)

    @classmethod
    def export_to_excel(
        cls, orders, weight: float = 1.0, store_name: str = ""
    ) -> HttpResponse:
        """
        Generate an .xlsx workbook using the official merchant_bulk_order_sample.xlsx template,
        preserving all built-in dropdown validations (Stores, Zones, Areas) and lookup formulas.
        """
        if os.path.exists(cls.TEMPLATE_PATH):
            wb = openpyxl.load_workbook(cls.TEMPLATE_PATH)
            ws = wb["Worksheet"] if "Worksheet" in wb.sheetnames else wb.active
            using_template = True
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Worksheet"
            ws.views.sheetView[0].showGridLines = True
            ws.append(cls.HEADERS)
            using_template = False

        row_count = 0
        exported_order_ids: List[int] = []

        for index, order in enumerate(orders, start=2):
            row_count += 1
            exported_order_ids.append(order.id)
            row_data = cls.prepare_order_row(
                order, weight=weight, store_name=store_name
            )

            if using_template:
                for col_idx, val in enumerate(row_data, start=1):
                    ws.cell(row=index, column=col_idx).value = val
            else:
                ws.append(row_data)

        if using_template:
            # Clean up template placeholder rows after the last exported order
            last_order_row = max(row_count + 1, 2)
            if ws.max_row > last_order_row:
                ws.delete_rows(last_order_row + 1, ws.max_row - last_order_row)

            # Ensure ListCities named range exists pointing to 'Dropdown List'!$C$2:$C${max_city_row}
            max_city_r = 317
            if "Dropdown List" in wb.sheetnames:
                ws_dd = wb["Dropdown List"]
                for r in range(2, ws_dd.max_row + 1):
                    if ws_dd.cell(row=r, column=3).value:
                        max_city_r = r

            if "ListCities" not in wb.defined_names:
                dn_cities = DefinedName(
                    "ListCities", attr_text=f"'Dropdown List'!$C$2:$C${max_city_r}"
                )
                wb.defined_names.add(dn_cities)

            # Link RecipientCity(*) (Column F) with ListCities dropdown
            dv_city = DataValidation(
                type="list", formula1="ListCities", allow_blank=True
            )
            ws.add_data_validation(dv_city)
            max_val_row = max(last_order_row, 100)
            dv_city.add(f"F2:F{max_val_row}")

            # If more than 99 orders, extend the template data validations
            if row_count > 99:
                for dv in ws.data_validations.dataValidation:
                    sqref_str = str(dv.sqref)
                    if "B2:B" in sqref_str:
                        dv.sqref = f"B2:B{last_order_row}"
                    elif "F2:F" in sqref_str:
                        dv.sqref = f"F2:F{last_order_row}"
                    elif "G2:G" in sqref_str:
                        dv.sqref = f"G2:G{last_order_row}"
                    elif "H2:H" in sqref_str:
                        dv.sqref = f"H2:H{last_order_row}"
        else:
            # Fallback data validation if template file is absent
            stores_formula = f'"{",".join(cls.STORE_NAMES)}"'
            dv_store_name = DataValidation(
                type="list", formula1=stores_formula, allow_blank=True
            )
            ws.add_data_validation(dv_store_name)
            max_r = max(row_count + 1, 100)
            dv_store_name.add(f"B2:B{max_r}")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

        # Update logistics to Pathao for exported orders
        if exported_order_ids:
            cls.update_orders_logistics(exported_order_ids, logistics="Pathao")

        # Prepare HTTP Response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        response["Content-Disposition"] = (
            f'attachment; filename="orders_export_{timestamp}.xlsx"'
        )
        wb.save(response)
        return response

    @classmethod
    def export_to_csv(
        cls, orders, weight: float = 1.0, store_name: str = ""
    ) -> HttpResponse:
        """
        Generate a downloadable CSV file with the same format.
        """
        response = HttpResponse(content_type="text/csv")
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        response["Content-Disposition"] = (
            f'attachment; filename="orders_export_{timestamp}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(cls.HEADERS)

        exported_order_ids: List[int] = []
        for order in orders:
            exported_order_ids.append(order.id)
            writer.writerow(
                cls.prepare_order_row(order, weight=weight, store_name=store_name)
            )

        # Update logistics to Pathao for exported orders
        if exported_order_ids:
            cls.update_orders_logistics(exported_order_ids, logistics="Pathao")

        return response
