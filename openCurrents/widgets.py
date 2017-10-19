class RadioWidget(forms.RadioSelect):
    class Media:
        css = {
            'all': ('custom-radio.css',)
        }

    def get_context(self, name, value, attrs):
        context = super(RadioWidget, self).get_context(name, value, attrs)
        context['widget']['attrs']['class'] = 'custom-radio'
        return context