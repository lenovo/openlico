import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)


class SecretKeyTask:
    is_running = True

    @classmethod
    def get_key_from_db(cls):
        from lico.core.base.models import SecretKey

        db_secret_key = SecretKey.objects.last()
        if db_secret_key and db_secret_key.key:
            return db_secret_key.key.decode()

    @classmethod
    def run(cls, web_secret_key):
        while cls.is_running:
            cls.once(web_secret_key)

            update_interval = settings.USER.KEY.get('UPDATE_INTERVAL')
            time.sleep(update_interval if update_interval else 100)

    @classmethod
    def once(cls, web_secret_key):
        web_secret_key.key_func = cls.get_key_from_db
        web_secret_key.update_keys()

    def terminal(self):
        self.is_running = False
