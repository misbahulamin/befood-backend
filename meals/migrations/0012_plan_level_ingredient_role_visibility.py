from django.db import migrations, models


def backfill_plan_line_roles(apps, schema_editor):
    MealCyclePlanLine = apps.get_model('meals', 'MealCyclePlanLine')
    Ingredient = apps.get_model('meals', 'Ingredient')
    ingredient_roles = dict(Ingredient.objects.values_list('id', 'product_role'))
    for line in MealCyclePlanLine.objects.all().iterator():
        role = ingredient_roles.get(line.ingredient_id) or 'other'
        MealCyclePlanLine.objects.filter(pk=line.pk).update(product_role=role)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0011_ops_catalog_public_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingredient',
            name='is_customer_visible',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'When false, ingredient is used for costing/admin schedules '
                    'but omitted from customer menus.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='mealcycleplanline',
            name='product_role',
            field=models.CharField(
                choices=[
                    ('main', 'Main'),
                    ('side', 'Side'),
                    ('staple', 'Staple'),
                    ('seasoning', 'Seasoning'),
                    ('other', 'Other'),
                ],
                help_text='Serving role for this ingredient within this meal package cycle plan.',
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_plan_line_roles, noop_reverse),
        migrations.AlterField(
            model_name='mealcycleplanline',
            name='product_role',
            field=models.CharField(
                choices=[
                    ('main', 'Main'),
                    ('side', 'Side'),
                    ('staple', 'Staple'),
                    ('seasoning', 'Seasoning'),
                    ('other', 'Other'),
                ],
                help_text='Serving role for this ingredient within this meal package cycle plan.',
                max_length=20,
            ),
        ),
        migrations.RemoveField(
            model_name='ingredient',
            name='product_role',
        ),
    ]
