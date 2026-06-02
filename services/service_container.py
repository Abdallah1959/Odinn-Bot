from typing import TYPE_CHECKING

# نستخدم TYPE_CHECKING لتجنب الـ Circular Imports والمحافظة على الـ Auto-complete في الـ IDE
if TYPE_CHECKING:
    from services.tmdb_service import TMDBService
    from services.database_service import DatabaseService

class ServiceContainer:
    """
    حاوية الخدمات (Service Container):
    مسؤولة عن تجميع كل الخدمات المركزية في مكان واحد لتسهيل الوصول إليها من أي مكان
    داخل البوت (مثل الـ Cogs) باستخدام: self.bot.services.tmdb و self.bot.services.db
    """
    def __init__(
        self, 
        tmdb_service: 'TMDBService', 
        database_service: 'DatabaseService'
    ):
        # [تعديل النسخة الأكثر اكتمالاً]: تثبيت حيازة الأنواع الصريحة لضمان الدعم الكامل للمحررات
        self.tmdb: 'TMDBService' = tmdb_service
        self.db: 'DatabaseService' = database_service
