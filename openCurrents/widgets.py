from django import forms

class RadioWidget(forms.RadioSelect):
    class Media:
        css = {
            'all': ('/static/css/custom-radio.css',)
        }

	# def __init__(self, attrs=None):
	# 	print 'calling init'
	#  	super(RadioWidget, self).__init__(
	#  		attrs.update({'class': 'custom-radio'})
	#  	)

    def get_context(self, name, value, attrs):
        context = super(RadioWidget, self).get_context(name, value, attrs)
        context['widget']['attrs']['class'] = 'custom-radio'

        return context


class TextWidget(forms.TextInput):
    def get_context(self, name, value, attrs):
        context = super(TextWidget, self).get_context(name, value, attrs)
        context['widget']['attrs']['class'] = 'center'

        return context
        