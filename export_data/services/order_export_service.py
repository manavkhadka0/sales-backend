import csv
from typing import List

import openpyxl
from django.db.models import Case, Prefetch, When
from django.http import HttpResponse
from django.utils import timezone
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
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

        # 6. RecipientCity(*) - blank as requested
        recipient_city = ""

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
        Generate an .xlsx workbook conforming to the required layout, complete with
        StoreName dropdown validation and auto-fitted columns.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Orders"
        ws.views.sheetView[0].showGridLines = True

        # Styles
        header_font = Font(name="Segoe UI", size=10, bold=True, color="1F2937")
        header_fill = PatternFill(
            start_color="F3F4F6", end_color="F3F4F6", fill_type="solid"
        )
        header_alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )

        thin_border = Border(
            left=Side(style="thin", color="E5E7EB"),
            right=Side(style="thin", color="E5E7EB"),
            top=Side(style="thin", color="E5E7EB"),
            bottom=Side(style="thin", color="E5E7EB"),
        )

        data_font = Font(name="Segoe UI", size=10)
        left_align = Alignment(horizontal="left", vertical="center")
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")

        # Write header row
        ws.append(cls.HEADERS)
        ws.row_dimensions[1].height = 28

        for col_idx in range(1, len(cls.HEADERS) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Write rows
        row_count = 0
        exported_order_ids: List[int] = []
        for index, order in enumerate(orders, start=2):
            row_count += 1
            exported_order_ids.append(order.id)
            row_data = cls.prepare_order_row(
                order, weight=weight, store_name=store_name
            )
            ws.append(row_data)
            ws.row_dimensions[index].height = 22

            for col_idx in range(1, len(cls.HEADERS) + 1):
                cell = ws.cell(row=index, column=col_idx)
                cell.font = data_font
                cell.border = thin_border

                # Alignment per column (1-indexed):
                # 1: ItemType, 3: MerchantOrderId, 5: RecipientPhone, 6: RecipientCity,
                # 7: RecipientZone, 11: ItemQuantity, 12: ItemWeight -> Center
                # 10: AmountToCollect -> Right
                # 2: StoreName, 4: RecipientName, 8: RecipientArea, 9: RecipientAddress,
                # 13: ItemDesc, 14: SpecialInstruction -> Left
                if col_idx in [1, 3, 5, 6, 7, 11, 12]:
                    cell.alignment = center_align
                elif col_idx == 10:
                    cell.alignment = right_align
                else:
                    cell.alignment = left_align

        max_row = max(row_count + 1, 100)

        # Add Data Validation for StoreName column (B)
        stores_formula = f'"{",".join(cls.STORE_NAMES)}"'
        dv_store_name = DataValidation(
            type="list", formula1=stores_formula, allow_blank=True
        )
        ws.add_data_validation(dv_store_name)
        dv_store_name.add(f"B2:B{max_row}")

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
