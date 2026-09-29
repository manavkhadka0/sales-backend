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
    export templates (Excel .xlsx and CSV .csv).
    """

    HEADERS: List[str] = [
        "Reference ID",
        "Order Type",
        "Customer Name",
        "Primary Mobile No.",
        "Secondary Mobile No.",
        "COD Amount",
        "Landmark",
        "City / Area",
        "Destination Branch",
        "Product Description",
        "Instruction",
        "weight",
    ]

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
            .select_related("location")
            .prefetch_related(
                Prefetch(
                    "order_products",
                    queryset=OrderProduct.objects.select_related("product__product"),
                )
            )
            .order_by(preserved_order)
        )

    @classmethod
    def prepare_order_row(cls, order: Order, weight: float = 1.0) -> list:
        """
        Transform an Order instance into the row format expected by the courier template.
        """
        # 1. Reference ID
        reference_id = order.order_code or str(order.id)

        # 2. Order Type (Fixed to 'Regular' as required)
        order_type = "Regular"

        # 3. Customer Name
        customer_name = order.full_name or ""

        # 4. Primary Mobile No.
        primary_mobile = order.phone_number or ""

        # 5. Secondary Mobile No.
        secondary_mobile = order.alternate_phone_number or ""

        # 6. COD Amount (total_amount - prepaid_amount)
        total = float(order.total_amount or 0)
        prepaid = float(order.prepaid_amount or 0)
        cod_val = total - prepaid
        cod_amount = int(cod_val) if cod_val.is_integer() else round(cod_val, 2)

        # 7. Landmark
        landmark = order.landmark or ""

        # 8. City / Area
        delivery_address = (order.delivery_address or "").strip()
        city = (order.city or "").strip()
        if delivery_address and city:
            if city.lower() in delivery_address.lower():
                city_area = delivery_address
            else:
                city_area = f"{delivery_address}, {city}"
        elif delivery_address:
            city_area = delivery_address
        elif city:
            city_area = city
        else:
            city_area = ""

        # 9. Destination Branch (location.name)
        destination_branch = order.location.name if order.location else ""

        # 10. Product Description
        product_items = []
        for op in order.order_products.all():
            try:
                p_name = op.product.product.name
            except AttributeError:
                p_name = "Product"
            product_items.append(f"{op.quantity}x {p_name}")
        product_description = ", ".join(product_items)

        # 11. Instruction
        instruction = order.remarks or ""

        # 12. weight
        try:
            numeric_weight = float(weight)
            formatted_weight = (
                int(numeric_weight)
                if numeric_weight.is_integer()
                else round(numeric_weight, 2)
            )
        except (ValueError, TypeError):
            formatted_weight = 1

        return [
            reference_id,
            order_type,
            customer_name,
            primary_mobile,
            secondary_mobile,
            cod_amount,
            landmark,
            city_area,
            destination_branch,
            product_description,
            instruction,
            formatted_weight,
        ]

    @classmethod
    def export_to_excel(cls, orders, weight: float = 1.0) -> HttpResponse:
        """
        Generate an .xlsx workbook conforming to the required layout, complete with
        Order Type dropdown validation and auto-fitted columns.
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
        for index, order in enumerate(orders, start=2):
            row_count += 1
            row_data = cls.prepare_order_row(order, weight=weight)
            ws.append(row_data)
            ws.row_dimensions[index].height = 22

            for col_idx in range(1, len(cls.HEADERS) + 1):
                cell = ws.cell(row=index, column=col_idx)
                cell.font = data_font
                cell.border = thin_border

                # Alignment per column:
                # 1: Ref ID, 2: Order Type, 4: Primary Mob, 5: Sec Mob, 9: Dest Branch, 12: weight -> Center
                # 6: COD Amount -> Right
                # 3: Customer Name, 7: Landmark, 8: City / Area, 10: Product Desc, 11: Instruction -> Left
                if col_idx in [1, 2, 4, 5, 9, 12]:
                    cell.alignment = center_align
                elif col_idx == 6:
                    cell.alignment = right_align
                else:
                    cell.alignment = left_align

        # Add Data Validation for Order Type column (B)
        dv_order_type = DataValidation(
            type="list", formula1='"Regular,Exchange,Return"', allow_blank=True
        )
        ws.add_data_validation(dv_order_type)
        max_row = max(row_count + 1, 100)
        dv_order_type.add(f"B2:B{max_row}")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

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
    def export_to_csv(cls, orders, weight: float = 1.0) -> HttpResponse:
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

        for order in orders:
            writer.writerow(cls.prepare_order_row(order, weight=weight))

        return response
