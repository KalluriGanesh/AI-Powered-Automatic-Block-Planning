from django.db import models


class MaintenanceRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SCHEDULED', 'Scheduled'),
        ('DEFERRED', 'Deferred'),
    ]

    SOURCE_CHOICES = [
        ('FORM', 'Form'),
        ('NL', 'Natural Language'),
        ('WHATIF', 'What-If'),
    ]

    asset = models.ForeignKey(
        'core.Asset',
        on_delete=models.CASCADE,
        related_name='maintenance_requests'
    )
    description = models.TextField(blank=True)
    duration_hours = models.PositiveSmallIntegerField()  # 1-8
    priority = models.PositiveSmallIntegerField()  # 1-5, 5 highest
    deadline_day = models.IntegerField()  # 0-6
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='FORM'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', 'deadline_day', 'created_at']

    @property
    def section(self):
        return self.asset.section

    def __str__(self):
        return f"Req #{self.pk} - {self.asset.name} (P{self.priority}, D{self.deadline_day}, {self.duration_hours}h)"
