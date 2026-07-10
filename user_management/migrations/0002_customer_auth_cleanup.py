from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customerprofile',
            name='avatar',
        ),
        migrations.RemoveField(
            model_name='customerprofile',
            name='default_address',
        ),
        migrations.RemoveField(
            model_name='address',
            name='customer',
        ),
        migrations.DeleteModel(
            name='Address',
        ),
        migrations.DeleteModel(
            name='DeviceToken',
        ),
        migrations.DeleteModel(
            name='RiderProfile',
        ),
        migrations.DeleteModel(
            name='StaffProfile',
        ),
        migrations.DeleteModel(
            name='UserActivityLog',
        ),
        migrations.AlterField(
            model_name='customerprofile',
            name='phone',
            field=models.CharField(max_length=10, unique=True),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='occupation',
            field=models.CharField(choices=[('student', 'Student'), ('job_holder', 'Job Holder'), ('freelancer', 'Freelancer'), ('business_owner', 'Business Owner'), ('unemployed', 'Unemployed'), ('other', 'Other')], default='student', max_length=30),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='is_bachelor',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='is_email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='email_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
