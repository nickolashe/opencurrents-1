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
  $( document ).on( 'touchend click', '.js-close-any', function ( event ) {
    if ( controller.getActiveSlidebar() ) {
      event.preventDefault();
      event.stopPropagation();
      controller.close();
    }
  } );
} );

// Google Analytics
(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','https://www.google-analytics.com/analytics.js','ga');

ga('create', 'UA-37260620-2', 'auto');
ga('send', 'pageview');
