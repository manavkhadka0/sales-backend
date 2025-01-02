from rest_framework import serializers
from .models import Project  # Import the Project model
from account.serializers import CustomUserSerializer

class ProjectSerializer(serializers.ModelSerializer):
    team=CustomUserSerializer(many=True)
    class Meta:
        model = Project
        fields = '__all__'  # Include all fields from the Project model
