from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Make sure to import these models
from .models import CustomUser, Distributor, Franchise, Factory
from .serializers import CustomUserSerializer, DistributorSerializer, LoginSerializer, FranchiseSerializer, FactorySerializer, SmallUserSerializer, UserSmallSerializer
from rest_framework_simplejwt.tokens import RefreshToken  # Import JWT token utilities
from rest_framework.permissions import AllowAny  # Import permission class
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import ChangePasswordSerializer


class UserListView(APIView):
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, phone_number=None):
        if phone_number:
            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                serializer = SmallUserSerializer(user)
                return Response(serializer.data)
            except CustomUser.DoesNotExist:
                return Response({'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if user.role == 'Admin':
            users = CustomUser.objects.all()
            serializer = CustomUserSerializer(users, many=True)
        elif user.role == 'Franchise':
            users = CustomUser.objects.filter(role='SalesPerson',
                                              franchise=user.franchise)
            serializer = SmallUserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Create a copy of the request data to modify
        data = request.data.copy()

        # Only set franchise if request.user exists and has a franchise
        if request.user and request.user.role == 'Franchise':
            data['franchise'] = request.user.franchise.id

        serializer = CustomUserSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, phone_number):
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            serializer = CustomUserSerializer(
                user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, phone_number):
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


class LoginView(APIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]  # Allow any user to access this view

    def post(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')

        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            if user.check_password(password):  # Check if the password is correct
                refresh = RefreshToken.for_user(user)  # Create JWT tokens
                user_serializer = CustomUserSerializer(
                    user)  # Serialize user data
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': user_serializer.data  # Include user details in response
                }, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


class UserProfileView(APIView):
    def get(self, request):
        user = request.user
        serializer = CustomUserSerializer(user)
        return Response(serializer.data)


class DistributorListCreateView(generics.ListCreateAPIView):
    queryset = Distributor.objects.all()
    serializer_class = DistributorSerializer


class FranchiseListCreateView(generics.ListCreateAPIView):
    queryset = Franchise.objects.all()
    serializer_class = FranchiseSerializer


class FactoryListCreateView(generics.ListCreateAPIView):
    queryset = Factory.objects.all()
    serializer_class = FactorySerializer


class FranchiseByDistributorView(APIView):
    def get(self, request, distributor_id):
        try:
            franchises = Franchise.objects.filter(
                distributor_id=distributor_id)
            serializer = FranchiseSerializer(franchises, many=True)
            return Response(serializer.data)
        except Franchise.DoesNotExist:
            return Response(
                {'error': 'No franchises found for this distributor'},
                status=status.HTTP_404_NOT_FOUND
            )


class ChangePassword(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        phone_number = request.data.get('phone_number')
        new_password = request.data.get('new_password')

        user = CustomUser.objects.get(phone_number=phone_number)
        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)


class UserFranchiseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get franchises based on the authenticated user's distributor
            franchises = Franchise.objects.filter(
                distributor=request.user.distributor)
            serializer = FranchiseSerializer(franchises, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': 'Error fetching franchises'},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserDistributorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get distributors based on the authenticated user's factory
            distributors = Distributor.objects.filter(
                factory=request.user.factory)
            serializer = DistributorSerializer(distributors, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': 'Error fetching distributors'},
                status=status.HTTP_400_BAD_REQUEST
            )
