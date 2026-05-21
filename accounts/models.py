from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    so_dien_thoai = models.CharField(max_length=15, blank=True, null=True)
    anh_dai_dien = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return self.user.username