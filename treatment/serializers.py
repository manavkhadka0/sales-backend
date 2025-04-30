from rest_framework import serializers
from .models import CustomerTreatment, Image


class ImageSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)  # For handling updates

    class Meta:
        model = Image
        fields = ['id', 'status', 'image', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CustomerTreatmentSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, required=False)

    class Meta:
        model = CustomerTreatment
        fields = ['id', 'name', 'address', 'phone_number',
                  'email', 'images', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        customer = CustomerTreatment.objects.create(**validated_data)

        # Create images
        for image_data in images_data:
            Image.objects.create(customer_treatment=customer, **image_data)

        return customer

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', [])

        # Update customer fields
        instance.name = validated_data.get('name', instance.name)
        instance.address = validated_data.get('address', instance.address)
        instance.phone_number = validated_data.get(
            'phone_number', instance.phone_number)
        instance.email = validated_data.get('email', instance.email)
        instance.save()

        # Keep track of existing image IDs
        existing_image_ids = set(instance.images.values_list('id', flat=True))
        updated_image_ids = set()

        # Update or create images
        for image_data in images_data:
            image_id = image_data.get('id')
            if image_id:  # Update existing image
                try:
                    image = instance.images.get(id=image_id)
                    for attr, value in image_data.items():
                        setattr(image, attr, value)
                    image.save()
                    updated_image_ids.add(image_id)
                except Image.DoesNotExist:
                    continue
            else:  # Create new image
                Image.objects.create(customer_treatment=instance, **image_data)

        # Delete images that weren't included in the update
        images_to_delete = existing_image_ids - updated_image_ids
        instance.images.filter(id__in=images_to_delete).delete()

        return instance
