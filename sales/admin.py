from django import forms
from django.contrib import admin
from django.db import models as django_models
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.widgets import (
    UnfoldAdminDateWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextInputWidget,
)

from account.models import CustomUser, Franchise

from .models import *

# Register your models here.


class LocationAdmin(ModelAdmin):
    list_display = ["name", "coverage_areas"]
    list_filter = ["logistics"]
    search_fields = ["name", "coverage_areas"]


class OrderProductInline(TabularInline):
    model = OrderProduct
    extra = 1


class OrderExportForm(SelectableFieldsExportForm):
    franchise = forms.ModelChoiceField(
        queryset=Franchise.objects.all(),
        required=False,
        label="Franchise",
        widget=UnfoldAdminSelectWidget,
    )
    sales_person = forms.ModelChoiceField(
        queryset=CustomUser.objects.all(),
        required=False,
        label="Sales Person",
        widget=UnfoldAdminSelectWidget,
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Location",
        widget=UnfoldAdminSelectWidget,
    )
    delivery_address = forms.CharField(
        required=False,
        label="Delivery Address",
        widget=UnfoldAdminTextInputWidget,
    )
    payment_method = forms.ChoiceField(
        choices=[("", "---")] + Order.PAYMENT_CHOICES,
        required=False,
        label="Payment Method",
        widget=UnfoldAdminSelectWidget,
    )
    total_amount_min = forms.DecimalField(
        required=False,
        label="Total Amount (Min)",
        widget=UnfoldAdminTextInputWidget,
    )
    total_amount_max = forms.DecimalField(
        required=False,
        label="Total Amount (Max)",
        widget=UnfoldAdminTextInputWidget,
    )
    logistics = forms.ChoiceField(
        choices=[("", "---")] + Order.LOGISTICS_CHOICES,
        required=False,
        label="Logistics",
        widget=UnfoldAdminSelectWidget,
    )
    start_date = forms.DateField(
        required=False,
        label="Start Date (Order Date)",
        widget=UnfoldAdminDateWidget(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        label="End Date (Order Date)",
        widget=UnfoldAdminDateWidget(attrs={"type": "date"}),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        required=False,
        label="Product",
        widget=UnfoldAdminSelectWidget,
    )
    product_quantity_min = forms.IntegerField(
        required=False,
        label="Product Quantity (Min)",
        widget=UnfoldAdminTextInputWidget,
    )
    products_count_min = forms.IntegerField(
        required=False,
        label="Products Count (Min)",
        widget=UnfoldAdminTextInputWidget,
    )
    products_count_max = forms.IntegerField(
        required=False,
        label="Products Count (Max)",
        widget=UnfoldAdminTextInputWidget,
    )
    more_than_3_products = forms.BooleanField(
        required=False,
        label="More than 3 Products",
    )
    multiple_orders_customer = forms.BooleanField(
        required=False,
        label="Multiple Orders by Same Customer",
    )
    oil_bottle_total_min = forms.IntegerField(
        required=False,
        label="Oil Bottle Total Quantity (Min)",
        widget=UnfoldAdminTextInputWidget,
    )
    oil_bottle_only = forms.BooleanField(
        required=False,
        label="Oil Bottle Only",
    )


class OrderResource(resources.ModelResource):
    franchise_name = fields.Field(
        attribute="franchise__name", column_name="Franchise Name"
    )
    date_time = fields.Field(column_name="Date Time")
    order_code = fields.Field(attribute="order_code", column_name="Order Code")
    full_name = fields.Field(attribute="full_name", column_name="Full Name")
    phone_number = fields.Field(attribute="phone_number", column_name="Phone Number")
    address = fields.Field(attribute="delivery_address", column_name="Address")
    order_products = fields.Field(column_name="Order Products")
    total_amount = fields.Field(attribute="total_amount", column_name="Total Amount")
    prepaid_amount = fields.Field(
        attribute="prepaid_amount", column_name="Prepaid Amount"
    )
    remarks = fields.Field(attribute="remarks", column_name="Remarks")

    class Meta:
        model = Order
        fields = (
            "franchise_name",
            "date_time",
            "order_code",
            "full_name",
            "phone_number",
            "address",
            "order_products",
            "total_amount",
            "prepaid_amount",
            "remarks",
        )
        export_order = (
            "franchise_name",
            "date_time",
            "order_code",
            "full_name",
            "phone_number",
            "address",
            "order_products",
            "total_amount",
            "prepaid_amount",
            "remarks",
        )

    def dehydrate_date_time(self, order):
        if order.created_at:
            return order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return ""

    def dehydrate_order_products(self, order):
        return ", ".join([
            f"{op.product.product.name}-{op.quantity}"
            for op in order.order_products.select_related("product__product").all()
        ])


class OrderAdmin(ModelAdmin, ImportExportModelAdmin):
    resource_classes = [OrderResource]
    import_form_class = ImportForm
    export_form_class = OrderExportForm

    def get_export_queryset(self, request):
        queryset = super().get_export_queryset(request)
        if request.POST:
            post_data = request.POST
            if post_data.get("franchise"):
                queryset = queryset.filter(franchise_id=post_data.get("franchise"))
            if post_data.get("sales_person"):
                queryset = queryset.filter(
                    sales_person_id=post_data.get("sales_person")
                )
            if post_data.get("location"):
                queryset = queryset.filter(location_id=post_data.get("location"))
            if post_data.get("delivery_address"):
                queryset = queryset.filter(
                    delivery_address__icontains=post_data.get("delivery_address")
                )
            if post_data.get("payment_method"):
                queryset = queryset.filter(
                    payment_method=post_data.get("payment_method")
                )
            if post_data.get("logistics"):
                queryset = queryset.filter(logistics=post_data.get("logistics"))
            if post_data.get("total_amount_min"):
                queryset = queryset.filter(
                    total_amount__gte=post_data.get("total_amount_min")
                )
            if post_data.get("total_amount_max"):
                queryset = queryset.filter(
                    total_amount__lte=post_data.get("total_amount_max")
                )
            if post_data.get("start_date"):
                queryset = queryset.filter(date__gte=post_data.get("start_date"))
            if post_data.get("end_date"):
                queryset = queryset.filter(date__lte=post_data.get("end_date"))
            if post_data.get("product"):
                queryset = queryset.filter(
                    order_products__product__product_id=post_data.get("product")
                )
            if post_data.get("product_quantity_min"):
                queryset = queryset.filter(
                    order_products__quantity__gte=post_data.get("product_quantity_min")
                )
            if post_data.get("products_count_min"):
                queryset = queryset.annotate(
                    p_count=django_models.Count("order_products")
                ).filter(p_count__gte=post_data.get("products_count_min"))
            if post_data.get("products_count_max"):
                queryset = queryset.annotate(
                    p_count=django_models.Count("order_products")
                ).filter(p_count__lte=post_data.get("products_count_max"))
            if post_data.get("more_than_3_products"):
                order_ids = []
                for order in queryset:
                    total_qty = sum(op.quantity for op in order.order_products.all())
                    max_qty = (
                        max(op.quantity for op in order.order_products.all())
                        if order.order_products.exists()
                        else 0
                    )
                    if max_qty >= 3 or total_qty >= 3:
                        order_ids.append(order.id)
                queryset = queryset.filter(id__in=order_ids)
            if post_data.get("multiple_orders_customer"):
                customers_with_multiple = (
                    Order.objects
                    .values("phone_number")
                    .annotate(order_count=django_models.Count("id"))
                    .filter(order_count__gt=1)
                    .values_list("phone_number", flat=True)
                )
                queryset = queryset.filter(phone_number__in=customers_with_multiple)
            if post_data.get("oil_bottle_total_min"):
                queryset = queryset.annotate(
                    oil_bottle_qty=django_models.Sum(
                        "order_products__quantity",
                        filter=django_models.Q(
                            order_products__product__product__name__icontains="oil bottle"
                        ),
                    )
                ).filter(oil_bottle_qty__gte=post_data.get("oil_bottle_total_min"))
            if post_data.get("oil_bottle_only"):
                queryset = queryset.annotate(
                    non_oil_item_count=django_models.Count(
                        "order_products",
                        filter=~django_models.Q(
                            order_products__product__product__name__icontains="oil bottle"
                        ),
                    ),
                    oil_bottle_qty=django_models.Sum(
                        "order_products__quantity",
                        filter=django_models.Q(
                            order_products__product__product__name__icontains="oil bottle"
                        ),
                    ),
                ).filter(non_oil_item_count=0, oil_bottle_qty__gt=0)

            queryset = queryset.distinct()
        return queryset

    list_display = [
        "full_name",
        "date",
        "get_sales_person_name",
        "franchise__name",
        "product_name",
        "delivery_address",
        "phone_number",
        "payment_method",
        "total_amount",
        "prepaid_amount",
        "order_status",
        "logistics",
    ]
    list_filter = [
        "sales_person",
        "order_products__product__product",
        "order_status",
        "created_at",
        "franchise__name",
    ]
    search_fields = ["full_name", "phone_number", "sales_person__first_name"]
    autocomplete_fields = ["sales_person"]

    def get_sales_person_name(self, obj):
        return obj.sales_person.first_name

    get_sales_person_name.short_description = "Sales Person"

    def product_name(self, obj):
        return ", ".join([
            f"{op.product.product.name} (Quantity: {op.quantity})"
            for op in obj.order_products.all()
        ])

    product_name.short_description = "Product Name"

    inlines = [OrderProductInline]


class ProductAdmin(ModelAdmin):
    list_display = ["name", "id", "is_factory_ingredient", "status"]
    list_editable = ["is_factory_ingredient", "status"]


class InventoryAdmin(ModelAdmin):
    list_display = ["product", "id", "distributor", "franchise", "quantity"]
    list_filter = ["distributor", "franchise", "factory"]


class InventoryChangeLogAdmin(ModelAdmin):
    list_filter = ["changed_at"]


class InventoryRequestItemInline(TabularInline):
    model = InventoryRequestItem
    extra = 1


class InventoryRequestAdmin(ModelAdmin):
    list_display = ["franchise"]
    list_filter = ["franchise"]
    inlines = [InventoryRequestItemInline]


admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Inventory, InventoryAdmin)
admin.site.register(Commission, ModelAdmin)
admin.site.register(InventoryChangeLog, InventoryChangeLogAdmin)
admin.site.register(InventoryRequest, InventoryRequestAdmin)
admin.site.register(PromoCode, ModelAdmin)
admin.site.register(Location, LocationAdmin)

admin.site.register(DatabaseMode, ModelAdmin)
admin.site.register(HistoricalDataConfig, ModelAdmin)
