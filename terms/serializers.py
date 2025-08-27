

from rest_framework import serializers
from .models import Terms

class TermsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Terms
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
