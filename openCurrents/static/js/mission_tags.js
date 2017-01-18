        $(document).ready(function() { 
        
        $(".hidden").hide().removeClass("hidden");
        
        $('#home-tags').change(function(){
            if ($('input:checked').length > 0) {
                $('#email-div').slideDown(500);
            }
        });
        
        var tagNum = 14;
        
        $('#add-tag-input').keypress(function (e) {
            var text = $(this).val();
                if (e.which == 13 && text != '') {
                    tagNum++;
                    $('#add-tag-input').val('');                       
                    $('#home-tags').append('<input value='+text+' id="home-tag-'+tagNum+'" class="vis-hidden" type="checkbox" name="home-tag[]" checked><label class="tag button small clear round" for="home-tag-'+tagNum+'">'+text+'</label>');
                    $('#email-div').slideDown(500);
                    e.preventDefault(); 
                    $(this).focus().select();
                }
                else if (e.which == 13 && text == ''){
                    e.preventDefault();
                    return false;
                };
        });
        
        $('#add-tag-button').click(function(){
            var text = $('#add-tag-input').val();
            if (text != '') {
                tagNum++;
                $('#add-tag-input').val('');                       
                $('#home-tags').append('<input value='+text+' id="home-tag-'+tagNum+'" class="vis-hidden" type="checkbox" name="home-tag[]" checked><label class="tag button small clear round" for="home-tag-'+tagNum+'">'+text+'</label>');
                $('#email-div').slideDown(500);
                e.preventDefault();
                $(this).focus().select();
            }
            else {
                e.preventDefault();
                return false;
            }
        });
    });