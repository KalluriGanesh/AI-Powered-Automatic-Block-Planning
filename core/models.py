from django.db import models


class Section(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    length_km = models.FloatField()
    is_blocked = models.BooleanField(default=False)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('TRACK', 'Track'),
        ('OHE', 'Overhead Equipment (OHE)'),
        ('SIGNAL', 'Signal'),
    ]

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='assets'
    )
    name = models.CharField(max_length=100)
    asset_type = models.CharField(
        max_length=10,
        choices=ASSET_TYPE_CHOICES
    )
    health_score = models.IntegerField(default=80)

    class Meta:
        ordering = ['section', 'asset_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_asset_type_display()}) - {self.section.code}"


class TrafficSlot(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='traffic_slots'
    )
    day = models.IntegerField()  # 0-6
    hour = models.IntegerField()  # 0-23
    density = models.IntegerField()  # 0-10

    class Meta:
        ordering = ['section', 'day', 'hour']
        unique_together = ('section', 'day', 'hour')

    def __str__(self):
        return f"{self.section.code} Day {self.day} {self.hour:02d}:00 - Density: {self.density}"
