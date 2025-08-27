from django.contrib import admin

# Register your models here.
from common.models import SEO, Review, Tag, SavedProduct 


admin.site.register(SEO)
admin.site.register(Review)
admin.site.register(Tag)
admin.site.register(SavedProduct)