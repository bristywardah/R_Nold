
from django.db import models

class Terms(models.Model):
    TYPE_CHOICES = (
        ('terms', 'Terms & Conditions'),
        ('privacy', 'Privacy Policy'),
    )

    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_type_display()} - {self.title}"

    class Meta:
        verbose_name = "Policy"
        verbose_name_plural = "Policies"
        ordering = ['-created_at']
