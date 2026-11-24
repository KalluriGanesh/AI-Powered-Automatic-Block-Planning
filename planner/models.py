from django.db import models


class PlanRun(models.Model):
    label = models.CharField(max_length=100, default='Optimized')
    created_at = models.DateTimeField(auto_now_add=True)
    horizon_days = models.IntegerField(default=7)
    is_baseline = models.BooleanField(default=False)
    is_whatif = models.BooleanField(default=False)
    total_requests = models.IntegerField(default=0)
    scheduled_count = models.IntegerField(default=0)
    deferred_count = models.IntegerField(default=0)
    conflicts = models.IntegerField(default=0)
    total_traffic_impact = models.FloatField(default=0.0)
    availability_pct = models.FloatField(default=100.0)
    deferred_reasons = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        kind = 'Baseline' if self.is_baseline else ('What-If' if self.is_whatif else 'Optimized')
        return f"PlanRun #{self.pk} [{kind}] - {self.label} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class Block(models.Model):
    plan_run = models.ForeignKey(
        PlanRun,
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    request = models.ForeignKey(
        'requests_app.MaintenanceRequest',
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    section = models.ForeignKey(
        'core.Section',
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    day = models.IntegerField()  # 0-6
    start_hour = models.IntegerField()  # 0-23
    end_hour = models.IntegerField()  # exclusive, maximum 24
    cost = models.FloatField(default=0.0)
    score_breakdown = models.JSONField(default=dict)
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ['day', 'start_hour']

    def __str__(self):
        return (
            f"Block #{self.pk} [{self.section.code}] Day {self.day} "
            f"{self.start_hour:02d}:00-{self.end_hour:02d}:00 (Req #{self.request_id})"
        )
