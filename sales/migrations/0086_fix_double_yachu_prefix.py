from django.db import migrations


def fix_double_prefix(apps, schema_editor):
    Product = apps.get_model("sales", "Product")
    Order = apps.get_model("sales", "Order")

    # Remove double prefix from Product images
    for product in Product.objects.all():
        if product.image:
            path = str(product.image)
            # If the path starts with yachuSales/yachuSales/, something is very wrong,
            # but usually it's just yachuSales/ being stored in DB while Storage adds another one.
            # The goal is to make sure DB paths don't start with yachuSales/ because PublicMediaStorage adds it.
            if path.startswith("yachuSales/"):
                new_path = path[len("yachuSales/") :]
                product.image = new_path
                product.save(update_fields=["image"])

    # Remove double prefix from Order payment screenshots
    for order in Order.objects.all():
        if order.payment_screenshot:
            path = str(order.payment_screenshot)
            if path.startswith("yachuSales/"):
                new_path = path[len("yachuSales/") :]
                order.payment_screenshot = new_path
                order.save(update_fields=["payment_screenshot"])


def reverse_fix(apps, schema_editor):
    # If we need to put it back (unlikely, but for safety)
    Product = apps.get_model("sales", "Product")
    Order = apps.get_model("sales", "Order")

    for product in Product.objects.all():
        if product.image:
            path = str(product.image)
            if not path.startswith("yachuSales/"):
                product.image = f"yachuSales/{path}"
                product.save(update_fields=["image"])

    for order in Order.objects.all():
        if order.payment_screenshot:
            path = str(order.payment_screenshot)
            if not path.startswith("yachuSales/"):
                order.payment_screenshot = f"yachuSales/{path}"
                order.save(update_fields=["payment_screenshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0085_alter_order_payment_screenshot_alter_product_image"),
    ]

    operations = [
        migrations.RunPython(fix_double_prefix, reverse_fix),
    ]
