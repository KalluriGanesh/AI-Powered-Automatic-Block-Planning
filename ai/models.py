from django.db import models


class AICache(models.Model):
    key = models.CharField(max_length=64, unique=True)  # SHA-256 of prompt
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AICache({self.key[:10]}...)"
