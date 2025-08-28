from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CustomUser, Distributor, Franchise, Factory, Logistics
from .serializers import CustomUserSerializer, DistributorSerializer, LoginSerializer, FranchiseSerializer, FactorySerializer, SmallUserSerializer, UserSerializer, UserSmallSerializer, LogisticsSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import ChangePasswordSerializer


class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    lookup_field = 'phone_number'

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserSerializer
        return CustomUserSerializer

    def perform_update(self, serializer):
        instance = serializer.instance
        new_phone = serializer.validated_data.get('phone_number')

        # If phone number is being updated, update username as well
        if new_phone and new_phone != instance.phone_number:
            serializer.validated_data['username'] = new_phone

        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        # instance.role = 'Others'
        instance.username = f"deleted_{instance.id}"
        instance.email = ""
        instance.phone_number = ""
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListView(APIView):
    serializer_class = CustomUserSerializer
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == 'SuperAdmin':
            users = CustomUser.objects.filter(
                factory=user.factory, is_deleted=False)
            serializer = CustomUserSerializer(users, many=True)
        elif user.role == 'Distributor':
            users = CustomUser.objects.filter(role__in=['SalesPerson', 'Treatment Staff', 'Packaging', 'Franchise'],
                                              distributor=user.distributor, is_deleted=False)
            serializer = SmallUserSerializer(users, many=True)
        elif user.role == 'Franchise':
            users = CustomUser.objects.filter(role__in=['SalesPerson', 'Treatment Staff', 'Packaging'],
                                              franchise=user.franchise, is_deleted=False)
            serializer = SmallUserSerializer(users, many=True)
        elif user.role == 'YDM_Logistics':
            users = CustomUser.objects.filter(
                role__in=["YDM_Logistics", "YDM_Operator", "YDM_Rider"], is_deleted=False)
            serializer = SmallUserSerializer(users, many=True)
        elif user.role == 'YDM_Operator':
            users = CustomUser.objects.filter(
                role__in=["YDM_Operator", "YDM_Rider"], is_deleted=False)
            serializer = SmallUserSerializer(users, many=True)
        else:
            return Response({'error': 'You do not have permission to view this resource.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(serializer.data)

    def post(self, request):
        # Create a copy of the request data to modify
        data = request.data.copy()

        if not request.user.is_authenticated or request.user.role in ('SuperAdmin', 'YDM_Rider', 'YDM_Logistics', 'YDM_Operator'):
            data['factory'] = None
            data['distributor'] = None
            data['franchise'] = None
            data['is_active'] = False
        else:
            if request.user.role == 'Franchise':
                data['franchise'] = request.user.franchise.id
                if request.user.franchise.distributor:
                    data['distributor'] = request.user.franchise.distributor.id
            elif request.user.factory:
                data['factory'] = request.user.factory.id
            else:
                data['factory'] = None

        serializer = CustomUserSerializer(data=data)
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        phone_number = user.phone_number
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        user = CustomUser.objects.get(phone_number=phone_number)
        if not user.check_password(old_password):
            return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)


class UserFranchiseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            if request.user.role == 'SuperAdmin':
                franchises = Franchise.objects.filter(
                    distributor__factory=request.user.factory)
            elif request.user.role == 'Distributor':
                franchises = Franchise.objects.filter(
                    distributor=request.user.distributor)
            elif request.user.role == 'Factory':
                franchises = Franchise.objects.filter(
                    distributor__factory=request.user.factory)
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


class LogisticsListCreateView(generics.ListCreateAPIView):
    queryset = Logistics.objects.all()
    serializer_class = LogisticsSerializer


class LogisticsDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Logistics.objects.all()
    serializer_class = LogisticsSerializer
    lookup_field = 'id'


class SalesPersonListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SmallUserSerializer

    def get_queryset(self):
        user = self.request.user

        if user.role in ['Franchise', 'Packaging']:
            # Get all sales persons for this franchise
            return CustomUser.objects.filter(
                franchise=user.franchise,
                role='SalesPerson',
                is_active=True,
                is_deleted=False
            )
        elif user.role == 'Distributor':
            # Get all sales persons for all franchises under this distributor
            franchises = Franchise.objects.filter(distributor=user.distributor)
            return CustomUser.objects.filter(
                franchise__in=franchises,
                role='SalesPerson',
                is_active=True,
                is_deleted=False
            )
        elif user.role == 'SuperAdmin':
            # Get all sales persons for all franchises under this factory
            franchises = Franchise.objects.filter(
                distributor__factory=user.factory)
            return CustomUser.objects.filter(
                franchise__in=franchises,
                role='SalesPerson',
                is_active=True,
                is_deleted=False
            )

        return CustomUser.objects.none()


class DemoUserList(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
