# Generated by Django 5.2.3 on 2025-06-14 12:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reciclaje', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('correo', models.EmailField(max_length=254, unique=True)),
                ('telefono', models.CharField(blank=True, max_length=15, null=True)),
                ('balance_puntos', models.IntegerField(default=0)),
                ('fecha_registro', models.DateField(auto_now_add=True)),
                ('contraseña', models.CharField(max_length=128)),
                ('ip', models.GenericIPAddressField(default='0.0.0.0')),
                ('id_rol', models.IntegerField(default=2)),
            ],
            options={
                'db_table': 'usuario',
                'managed': True,
            },
        ),
    ]
