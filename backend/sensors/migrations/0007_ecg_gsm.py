# Generated manually for ECG + GSM queue

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0006_outbound_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='livesensorreading',
            name='ecg_raw',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='livesensorreading',
            name='ecg_bpm',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='livesensorreading',
            name='ecg_mv',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='livesensorreading',
            name='ecg_waveform',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='patientlivestate',
            name='ecg_raw',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='patientlivestate',
            name='ecg_bpm',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='patientlivestate',
            name='ecg_mv',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='patientlivestate',
            name='ecg_status',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='patientlivestate',
            name='ecg_waveform',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name='GsmCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_id', models.CharField(default='ESP32-001', max_length=100)),
                ('patient_code', models.CharField(blank=True, default='', max_length=20)),
                ('channel', models.CharField(choices=[('sms', 'SMS'), ('call', 'Appel')], max_length=10)),
                ('phone', models.CharField(max_length=40)),
                ('message', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('sent', 'Envoyé'), ('failed', 'Échec')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('fall_event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gsm_commands', to='sensors.fallevent')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='gsmcommand',
            index=models.Index(fields=['device_id', 'status', 'created_at'], name='sensors_gsm_device__a8f3c1_idx'),
        ),
    ]
