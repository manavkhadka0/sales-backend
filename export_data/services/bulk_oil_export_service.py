from collections import defaultdict
from datetime import date
from typing import Dict, List, Set

import openpyxl
from django.http import HttpResponse
from django.utils import timezone
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from export_data.utils import sanitize_sheet_title
from sales.models import Order


class BulkOilExportService:
    """
    Service responsible for compiling bulk oil orders into a multi-sheet
    Excel workbook, with dedicated sheets for each franchise and an overview sheet.
    Summarizes total bulk order count and total oil bottle count (without revenue figures).
    """

    HEADERS: List[str] = [
        "S.N.",
        "Customer Name",
        "Date of Purchase",
        "Phone Number",
        "Alternate Phone",
        "Location",
        "Delivery Address",
        "City",
        "Landmark",
        "Franchise",
        "Oil Bottles Qty",
        "Bulk Oil Items",
        "All Products Ordered",
        "Payment Method",
        "Order Status",
        "Order Code",
        "Remarks",
    ]

    # Styling definitions
    HEADER_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(
        start_color="1F497D", end_color="1F497D", fill_type="solid"
    )
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

    DATA_FONT = Font(name="Segoe UI", size=10)
    DATA_ALIGNMENT_LEFT = Alignment(horizontal="left", vertical="center")
    DATA_ALIGNMENT_CENTER = Alignment(horizontal="center", vertical="center")

    TOTAL_FONT = Font(name="Segoe UI", size=10, bold=True)
    TOTAL_FILL = PatternFill(
        start_color="E9EDF4", end_color="E9EDF4", fill_type="solid"
    )

    THIN_BORDER_SIDE = Side(style="thin", color="D9D9D9")
    DATA_BORDER = Border(
        left=THIN_BORDER_SIDE,
        right=THIN_BORDER_SIDE,
        top=THIN_BORDER_SIDE,
        bottom=THIN_BORDER_SIDE,
    )

    TOTAL_TOP_BORDER = Side(style="thin", color="1F497D")
    TOTAL_BOTTOM_BORDER = Side(style="double", color="1F497D")
    TOTAL_BORDER = Border(
        left=THIN_BORDER_SIDE,
        right=THIN_BORDER_SIDE,
        top=TOTAL_TOP_BORDER,
        bottom=TOTAL_BOTTOM_BORDER,
    )

    @classmethod
    def build_excel_workbook(
        cls,
        orders: List[Order],
        start_date: date,
        end_date: date,
    ) -> openpyxl.Workbook:
        """
        Creates an openpyxl Workbook containing:
        1. Overview Summary sheet with franchise breakdown (Total Bulk Orders & Total Oil Bottles).
        2. All Bulk Orders sheet.
        3. A separate sheet for each franchise with bulk orders.
        """
        wb = openpyxl.Workbook()
        used_sheet_titles: Set[str] = set()

        # Group orders by franchise name
        franchise_orders_map: Dict[str, List[Order]] = defaultdict(list)
        for order in orders:
            franchise_name = getattr(
                order, "annotated_franchise_name", "Direct / Unassigned"
            )
            franchise_orders_map[franchise_name].append(order)

        # 1. Overview Summary sheet (first sheet)
        overview_sheet = wb.active
        overview_sheet.title = sanitize_sheet_title(
            "Overview Summary", used_sheet_titles
        )
        cls._populate_overview_sheet(
            overview_sheet,
            franchise_orders_map,
            start_date=start_date,
            end_date=end_date,
            total_orders_count=len(orders),
        )

        # 2. All Orders sheet
        all_orders_sheet = wb.create_sheet(
            title=sanitize_sheet_title("All Bulk Orders", used_sheet_titles)
        )
        cls._populate_orders_sheet(
            all_orders_sheet, orders, sheet_label="All Franchises"
        )

        # 3. Individual Franchise sheets
        for franchise_name in sorted(franchise_orders_map.keys()):
            f_orders = franchise_orders_map[franchise_name]
            sheet_title = sanitize_sheet_title(franchise_name, used_sheet_titles)
            ws = wb.create_sheet(title=sheet_title)
            cls._populate_orders_sheet(ws, f_orders, sheet_label=franchise_name)

        return wb

    @classmethod
    def _populate_overview_sheet(
        cls,
        ws,
        franchise_orders_map: Dict[str, List[Order]],
        start_date: date,
        end_date: date,
        total_orders_count: int,
    ) -> None:
        """Populates the executive overview summary sheet focused on bulk order & bottle counts."""
        ws.views.sheetView[0].showGridLines = True

        # Report Title Block
        title_font = Font(name="Segoe UI", size=14, bold=True, color="1F497D")
        sub_font = Font(name="Segoe UI", size=10, italic=True, color="595959")

        ws["A1"] = "Bulk Oil Orders Summary"
        ws["A1"].font = title_font

        ws["A2"] = (
            f"Period: {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')} "
            f"| Minimum Threshold: 3+ Oil Bottles per Order | Total Bulk Orders: {total_orders_count}"
        )
        ws["A2"].font = sub_font

        ws.row_dimensions[1].height = 24
        ws.row_dimensions[2].height = 18
        ws.row_dimensions[3].height = 10  # blank spacing row

        headers = [
            "S.N.",
            "Franchise Name",
            "Total Bulk Orders",
            "Total Oil Bottles",
        ]

        header_row = 4
        ws.row_dimensions[header_row].height = 26
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col_idx, value=h)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = cls.HEADER_ALIGNMENT

        grand_total_orders = 0
        grand_total_bottles = 0

        current_row = 5
        for idx, (franchise_name, f_orders) in enumerate(
            sorted(franchise_orders_map.items()), 1
        ):
            orders_cnt = len(f_orders)
            bottles_cnt = sum(
                getattr(o, "annotated_oil_bottle_qty", 0) for o in f_orders
            )

            grand_total_orders += orders_cnt
            grand_total_bottles += bottles_cnt

            row_data = [
                idx,
                franchise_name,
                orders_cnt,
                bottles_cnt,
            ]

            ws.row_dimensions[current_row].height = 20
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = cls.DATA_FONT
                cell.border = cls.DATA_BORDER
                if col_idx in [1, 3, 4]:
                    cell.alignment = cls.DATA_ALIGNMENT_CENTER
                else:
                    cell.alignment = cls.DATA_ALIGNMENT_LEFT

            current_row += 1

        # Summary / Grand Total Row
        ws.row_dimensions[current_row].height = 24
        total_data = [
            "Total",
            f"{len(franchise_orders_map)} Franchises",
            grand_total_orders,
            grand_total_bottles,
        ]

        for col_idx, val in enumerate(total_data, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.font = cls.TOTAL_FONT
            cell.fill = cls.TOTAL_FILL
            cell.border = cls.TOTAL_BORDER
            if col_idx in [1, 3, 4]:
                cell.alignment = cls.DATA_ALIGNMENT_CENTER
            else:
                cell.alignment = cls.DATA_ALIGNMENT_LEFT

        cls._autofit_columns(ws, min_width=12, max_width=40)

    @classmethod
    def _populate_orders_sheet(
        cls,
        ws,
        orders: List[Order],
        sheet_label: str,
    ) -> None:
        """Populates an orders table worksheet."""
        ws.views.sheetView[0].showGridLines = True

        # Header Row
        ws.row_dimensions[1].height = 28
        for col_idx, header in enumerate(cls.HEADERS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = cls.HEADER_ALIGNMENT

        total_oil_bottles = 0

        for row_idx, order in enumerate(orders, 2):
            oil_qty = getattr(order, "annotated_oil_bottle_qty", 0)
            bulk_items = getattr(order, "annotated_bulk_oil_items", "")
            all_items = getattr(order, "annotated_all_items", "")
            purchase_date = getattr(order, "annotated_purchase_date", "")
            location_name = getattr(order, "annotated_location_name", "")
            franchise_name = getattr(order, "annotated_franchise_name", "")

            total_oil_bottles += oil_qty

            row_data = [
                row_idx - 1,  # S.N.
                order.full_name or "",
                purchase_date,
                order.phone_number or "",
                order.alternate_phone_number or "",
                location_name,
                order.delivery_address or "",
                order.city or "",
                order.landmark or "",
                franchise_name,
                oil_qty,
                bulk_items,
                all_items,
                order.payment_method or "",
                order.order_status or "",
                order.order_code or "",
                order.remarks or "",
            ]

            ws.row_dimensions[row_idx].height = 20
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = cls.DATA_FONT
                cell.border = cls.DATA_BORDER

                # Alignment per column type
                if col_idx in [1, 3, 4, 5, 11, 14, 15, 16]:
                    cell.alignment = cls.DATA_ALIGNMENT_CENTER
                else:
                    cell.alignment = cls.DATA_ALIGNMENT_LEFT

        # Summary Row at the bottom of the table
        summary_row_idx = len(orders) + 2
        ws.row_dimensions[summary_row_idx].height = 24

        summary_values = {
            1: "Total",
            2: f"{len(orders)} Bulk Orders",
            11: total_oil_bottles,
        }

        for col_idx in range(1, len(cls.HEADERS) + 1):
            val = summary_values.get(col_idx, "")
            cell = ws.cell(row=summary_row_idx, column=col_idx, value=val)
            cell.font = cls.TOTAL_FONT
            cell.fill = cls.TOTAL_FILL
            cell.border = cls.TOTAL_BORDER

            if col_idx in [1, 11]:
                cell.alignment = cls.DATA_ALIGNMENT_CENTER
            else:
                cell.alignment = cls.DATA_ALIGNMENT_LEFT

        cls._autofit_columns(ws, min_width=10, max_width=50)

    @classmethod
    def _autofit_columns(cls, ws, min_width: int = 10, max_width: int = 50) -> None:
        """Dynamically adjusts column widths based on maximum content length."""
        for col in ws.columns:
            max_len = 0
            first_cell = col[0]
            col_letter = get_column_letter(first_cell.column)
            for cell in col:
                if cell.value is not None:
                    # Ignore title row spanning for width calculation
                    if cell.row in [1, 2] and ws.title.startswith("Overview"):
                        continue
                    cell_len = len(str(cell.value))
                    if cell_len > max_len:
                        max_len = cell_len
            adjusted_width = max(max_len + 4, min_width)
            ws.column_dimensions[col_letter].width = min(adjusted_width, max_width)

    @classmethod
    def export_to_excel_response(
        cls,
        orders: List[Order],
        start_date: date,
        end_date: date,
    ) -> HttpResponse:
        """
        Builds the Excel workbook and streams it in an HTTP response
        formatted for immediate browser / Postman download.
        """
        wb = cls.build_excel_workbook(orders, start_date=start_date, end_date=end_date)

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"bulk_oil_orders_{start_date.strftime('%Y%m%d')}_to_"
            f"{end_date.strftime('%Y%m%d')}_{timestamp}.xlsx"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        wb.save(response)
        return response
