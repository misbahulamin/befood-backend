import uuid

from django.db import migrations, models

import sliders.utils.slider_image


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='HomeSlider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('image', models.ImageField(upload_to=sliders.utils.slider_image.slider_image_upload_path)),
                ('priority', models.PositiveIntegerField(default=0, help_text='Lower values appear first on the home carousel.')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'home slider',
                'verbose_name_plural': 'home sliders',
                'ordering': ['priority', 'created_at', 'id'],
            },
        ),
    ]
