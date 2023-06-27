from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0001_lico_base_1_0_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='SecretKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('key', models.BinaryField(max_length=128)),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('update_time', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
