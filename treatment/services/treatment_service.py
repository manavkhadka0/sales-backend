from django.db import transaction

from treatment.models import CustomerTreatment, Image, PaymentHistory, TreatmentType


class TreatmentService:
    @staticmethod
    def is_periodic_image_type(treatment_type):
        """
        Checks if the treatment type is Package Member or Bottle Member
        which supports periodic 4-day image uploads.
        """
        return treatment_type in [
            TreatmentType.PACKAGE_MEMBER,
            TreatmentType.BOTTLE_MEMBER,
        ]

    @staticmethod
    def validate_day_number(treatment_type, day_number):
        """
        Validates day number for periodic image upload (e.g., 1, 4, 8, 12...).
        """
        if day_number is not None:
            if day_number < 1:
                raise ValueError("Day number must be greater than or equal to 1.")

    @classmethod
    @transaction.atomic
    def create_customer_treatment(
        cls, validated_data, images_data=None, initial_payment_data=None
    ):
        """
        Creates a new CustomerTreatment record, attaches images, and automatically records initial payment in PaymentHistory.
        """
        images_from_val = validated_data.pop("images", None)
        passed_images_data = validated_data.pop("images_data", None)
        passed_initial_payment = validated_data.pop("initial_payment_data", None)

        images = images_from_val or passed_images_data or images_data or []
        payment_info = passed_initial_payment or initial_payment_data

        customer = CustomerTreatment.objects.create(**validated_data)

        # Attach progress images if provided
        for img_data in images:
            if isinstance(img_data, dict):
                day_number = img_data.get("day_number")
                cls.validate_day_number(customer.treatment_type, day_number)
                Image.objects.create(customer_treatment=customer, **img_data)

        # Automatically record initial payment history entry if customer paid an amount on registration
        if customer.treatment_type != TreatmentType.FREE_SERVICE:
            payment_amount = None
            if payment_info and isinstance(payment_info, dict) and payment_info.get("amount"):
                payment_amount = float(payment_info.get("amount"))
            elif customer.paid_amount is not None and float(customer.paid_amount) > 0:
                payment_amount = float(customer.paid_amount)
            elif customer.total_amount is not None and float(customer.total_amount) > 0:
                payment_amount = float(customer.total_amount)

            if payment_amount and payment_amount > 0:
                if customer.paid_amount is None:
                    customer.paid_amount = payment_amount
                    customer.save(update_fields=["paid_amount"])

                PaymentHistory.objects.create(
                    customer_treatment=customer,
                    amount=payment_amount,
                    payment_method=customer.payment_method or "cash",
                    payment_screenshot=customer.payment_screenshot,
                    remarks="Initial payment on registration",
                    created_by=customer.service_by,
                )

        return customer

    @classmethod
    @transaction.atomic
    def update_customer_treatment(
        cls, instance, validated_data, images_data=None, delete_image_ids=None
    ):
        """
        Updates an existing CustomerTreatment record and manages associated images.
        """
        images_from_val = validated_data.pop("images", None)
        passed_images_data = validated_data.pop("images_data", None)
        passed_delete_ids = validated_data.pop("delete_image_ids", None)

        images = images_from_val or passed_images_data or images_data or []
        del_ids = passed_delete_ids or delete_image_ids

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if del_ids:
            instance.images.filter(id__in=del_ids).delete()

        existing_image_ids = set(instance.images.values_list("id", flat=True))
        updated_image_ids = set()

        for img_data in images:
            if isinstance(img_data, dict):
                img_id = img_data.get("id")
                day_number = img_data.get("day_number")
                cls.validate_day_number(instance.treatment_type, day_number)

                if img_id and img_id in existing_image_ids:
                    img_obj = Image.objects.get(id=img_id, customer_treatment=instance)
                    for attr, val in img_data.items():
                        if attr != "id":
                            setattr(img_obj, attr, val)
                    img_obj.save()
                    updated_image_ids.add(img_id)
                else:
                    Image.objects.create(customer_treatment=instance, **img_data)

        return instance

    @classmethod
    @transaction.atomic
    def record_payment(
        cls,
        customer_treatment,
        amount,
        payment_method="online",
        payment_screenshot=None,
        remarks=None,
        created_by=None,
    ):
        """
        Records a new payment for a CustomerTreatment.
        """
        return PaymentHistory.objects.create(
            customer_treatment=customer_treatment,
            amount=amount,
            payment_method=payment_method,
            payment_screenshot=payment_screenshot,
            remarks=remarks,
            created_by=created_by,
        )
