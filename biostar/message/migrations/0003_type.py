# Generated by Django 2.2 on 2019-04-17 18:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('message', '0002_sender'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='type',
            field=models.IntegerField(choices=[(0, 'Local messages'), (1, 'Email for every new post added to current one.'), (2, 'Email for every new thread (mailing list mode)')], db_index=True, default=0),
        ),
    ]