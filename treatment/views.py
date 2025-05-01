from django.shortcuts import render, get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import CustomerTreatment, Image
from .serializers import CustomerTreatmentSerializer, ImageSerializer
import json


def parse_json_data(data, field_name):
    """Helper function to parse JSON data from request"""
    if isinstance(data.get(field_name), list):
        return data.get(field_name)
    elif hasattr(data, 'getlist'):
        data_str = data.get(field_name)
        if data_str:
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid {field_name} format")
    return None


def validate_image_data(image_data):
    """Helper function to validate image data"""
    if not isinstance(image_data, dict):
        raise ValueError('Each image item must be a dictionary')
    if 'image' not in image_data or 'status' not in image_data:
        raise ValueError('Each image item must contain both image and status')
    return True


def create_images_for_customer(customer, images_data):
    """Helper function to create images for a customer"""
    if not images_data:
        return

    for image_data in images_data:
        validate_image_data(image_data)
        Image.objects.create(
            customer_treatment=customer,
            image=image_data['image'],
            status=image_data['status']
        )


class CustomerTreatmentListCreateView(generics.ListCreateAPIView):
    queryset = CustomerTreatment.objects.all()
    serializer_class = CustomerTreatmentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        try:
            data = request.data.copy()
            images_data = parse_json_data(request.data, 'images_data')

            # Create customer data dictionary
            customer_data = {
                field: request.data.get(field)
                for field in ['name', 'address', 'phone_number', 'email']
            }

            # Create customer
            customer_serializer = self.get_serializer(data=customer_data)
            customer_serializer.is_valid(raise_exception=True)
            customer = customer_serializer.save()

            # Handle images
            create_images_for_customer(customer, images_data)

            return Response(
                self.get_serializer(customer).data,
                status=status.HTTP_201_CREATED
            )

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to create customer treatment: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class CustomerTreatmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomerTreatment.objects.all()
    serializer_class = CustomerTreatmentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            # Parse images data and deletions
            images_data = parse_json_data(request.data, 'images_data')
            images_to_delete = parse_json_data(request.data, 'delete_images')

            # Get modified fields
            modified_data = {
                field: request.data.get(field)
                for field in ['name', 'address', 'phone_number', 'email']
                if field in request.data
            }

            # Update instance
            serializer = self.get_serializer(
                instance,
                data=modified_data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            customer = serializer.save()

            # Handle deletions
            if images_to_delete:
                instance.images.filter(id__in=images_to_delete).delete()

            # Handle new images
            create_images_for_customer(customer, images_data)

            return Response(serializer.data)

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update customer treatment: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class ImageListCreateView(generics.ListCreateAPIView):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    parser_classes = (MultiPartParser, FormParser)

    def create(self, request, *args, **kwargs):
        customer_treatment = get_object_or_404(
            CustomerTreatment,
            id=request.data.get('customer_treatment')
        )

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(customer_treatment=customer_treatment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    parser_classes = (MultiPartParser, FormParser)
