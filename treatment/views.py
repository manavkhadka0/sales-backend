from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import CustomerTreatment, Image
from .serializers import CustomerTreatmentSerializer, ImageSerializer

# Create your views here.


class CustomerTreatmentListCreateView(generics.ListCreateAPIView):
    queryset = CustomerTreatment.objects.all()
    serializer_class = CustomerTreatmentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        # Handle both form-data and JSON requests
        if request.content_type == 'application/json':
            return super().create(request, *args, **kwargs)

        # Handle multipart form-data
        customer_data = {
            'name': request.data.get('name'),
            'address': request.data.get('address'),
            'phone_number': request.data.get('phone_number'),
            'email': request.data.get('email'),
        }

        # Create customer first
        customer_serializer = self.get_serializer(data=customer_data)
        customer_serializer.is_valid(raise_exception=True)
        customer = customer_serializer.save()

        # Handle multiple images
        images = request.FILES.getlist('images')
        # List of 'Before' or 'After'
        statuses = request.data.getlist('statuses')

        if len(images) != len(statuses):
            return Response(
                {'error': 'Number of images and statuses must match'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create images
        for image, status in zip(images, statuses):
            Image.objects.create(
                customer_treatment=customer,
                image=image,
                status=status
            )

        # Return the complete customer data with images
        return Response(
            self.get_serializer(customer).data,
            status=status.HTTP_201_CREATED
        )


class CustomerTreatmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomerTreatment.objects.all()
    serializer_class = CustomerTreatmentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        if request.content_type == 'application/json':
            return super().update(request, *args, **kwargs)

        # Handle multipart form-data update
        customer_data = {
            'name': request.data.get('name', instance.name),
            'address': request.data.get('address', instance.address),
            'phone_number': request.data.get('phone_number', instance.phone_number),
            'email': request.data.get('email', instance.email),
        }

        # Update customer data
        serializer = self.get_serializer(
            instance, data=customer_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Handle image deletions
        images_to_delete = request.data.getlist('delete_images')
        if images_to_delete:
            instance.images.filter(id__in=images_to_delete).delete()

        # Handle new images
        new_images = request.FILES.getlist('new_images')
        new_statuses = request.data.getlist('new_statuses')

        if len(new_images) != len(new_statuses):
            return Response(
                {'error': 'Number of new images and statuses must match'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Add new images
        for image, status in zip(new_images, new_statuses):
            Image.objects.create(
                customer_treatment=instance,
                image=image,
                status=status
            )

        return Response(self.get_serializer(instance).data)


class ImageListCreateView(generics.ListCreateAPIView):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    parser_classes = (MultiPartParser, FormParser)

    def create(self, request, *args, **kwargs):
        customer_treatment_id = request.data.get('customer_treatment')
        try:
            customer_treatment = CustomerTreatment.objects.get(
                id=customer_treatment_id)
        except CustomerTreatment.DoesNotExist:
            return Response(
                {'error': 'Customer treatment not found'},
                status=status.HTTP_404_NOT_FOUND
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
