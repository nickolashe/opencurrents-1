    $(document).ready(function() { 
        
        $(".hidden").hide().removeClass("hidden");
        
        $('#home-tags').change(function(){
            if ($('input:checked').length > 0) {
                $('#email-div').slideDown(500);
            }
        });
        
        var tagNum = 14;
        
        $('#add-tag-input').keypress(function (z) {
            var text = $(this).val();
            if (z.which == 13 && text != '') {
                tagNum++;
                $('#add-tag-input').val('');                       
                $('#home-tags').append('<input value='+text+' id="home-tag-'+tagNum+'" class="vis-hidden" type="checkbox" name="home-tag[]" checked><label class="tag button small clear round" for="home-tag-'+tagNum+'">'+text+'</label>');
                $('#email-div').slideDown(500);
                z.preventDefault(); 
                $(this).select();
            }
            else if (z.which == 13 && text == ''){
                z.preventDefault();
                return false;
            };
        });
        
        $('#add-tag-button').click(function(z){
            var text = $('#add-tag-input').val();
            if (text != '') {
                tagNum++;
                $('#add-tag-input').val('');                       
                $('#home-tags').append('<input value='+text+' id="home-tag-'+tagNum+'" class="vis-hidden" type="checkbox" name="home-tag[]" checked><label class="tag button small clear round" for="home-tag-'+tagNum+'">'+text+'</label>');
                $('#email-div').slideDown(500);
                z.preventDefault();
                $(this).select();
            }
            else {
                z.preventDefault();
                return false;
            }
        });
        
        $('#home-tags').on('click', 'label', (function(){
            $(this).blur();
        }));
        
        $('#home-tags').on('touchend', function () {
              $(this).trigger('mouseout');
        });
        
        $(function() {
          $('a[href*="#"]:not([href="#"])').click(function() {
            if (location.pathname.replace(/^\//,'') == this.pathname.replace(/^\//,'') && location.hostname == this.hostname) {
              var target = $(this.hash);
              target = target.length ? target : $('[name=' + this.hash.slice(1) +']');
              if (target.length) {
                $('html, body').animate({
                  scrollTop: target.offset().top
                }, 1000);
                return false;
              }
            }
          });
        });
    });