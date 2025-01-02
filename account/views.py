from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CustomUser
from .serializers import CustomUserSerializer,DistributorSerializer,LoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken  # Import JWT token utilities
from rest_framework.permissions import AllowAny  # Import permission class

class UserListView(APIView):
    serializer_class = CustomUserSerializer
    def get(self, request):
        users = CustomUser.objects.all()
        serializer = CustomUserSerializer(users, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

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
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        

class UserProfileView(APIView):
    def get(self, request):
        user = request.user
        serializer = CustomUserSerializer(user)
        return Response(serializer.data)
    

