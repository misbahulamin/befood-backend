from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0024_delivery_sub_locations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicetoken',
            name='token',
            field=models.CharField(max_length=512, unique=True),
        ),
    ]
