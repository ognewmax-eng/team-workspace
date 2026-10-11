# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='theme',
            field=models.CharField(
                choices=[('light', 'Светлая'), ('dark', 'Темная'), ('auto', 'Автоматически')],
                default='light',
                help_text='Выберите тему оформления интерфейса',
                max_length=20,
                verbose_name='Тема оформления'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='primary_color',
            field=models.CharField(
                default='#2563eb',
                help_text='Основной цвет интерфейса в формате HEX (например, #2563eb)',
                max_length=7,
                verbose_name='Основной цвет'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='accent_color',
            field=models.CharField(
                default='#FF6B35',
                help_text='Акцентный цвет для выделения элементов в формате HEX (например, #FF6B35)',
                max_length=7,
                verbose_name='Акцентный цвет'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='font_size',
            field=models.CharField(
                choices=[('small', 'Маленький'), ('medium', 'Средний'), ('large', 'Большой')],
                default='medium',
                help_text='Размер шрифта интерфейса',
                max_length=10,
                verbose_name='Размер шрифта'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='compact_mode',
            field=models.BooleanField(
                default=False,
                help_text='Уменьшить отступы и размеры элементов для более компактного отображения',
                verbose_name='Компактный режим'
            ),
        ),
    ]
