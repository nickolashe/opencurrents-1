$(document).ready(function(){
	$('input, textarea').placeholder();

      $('a').on('click', (function(){
              $(this).blur();
          }));
});

$( '#nav li:has(ul)' ).doubleTapToGo();

( function ( $ ) {
  // Initialize Slidebars
  var controller = new slidebars();
  controller.init();
} ) ( jQuery );

// Initialize Slidebars
var controller = new slidebars();
controller.init();

// Toggle Slidebars
$( '.toggle-menu' ).on( 'click', function ( event ) {
  // Stop default action and bubbling
  event.stopPropagation();
  event.preventDefault();

  // Toggle the Slidebar with id 'id-1'
  controller.toggle( 'menu' );
  
  // Close any
  $( document ).on( 'click', '.js-close-any', function ( event ) {
    if ( controller.getActiveSlidebar() ) {
      event.preventDefault();
      event.stopPropagation();
      controller.close();
    }
  } );
} );