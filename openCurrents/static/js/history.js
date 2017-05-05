/*
 * Lets you use your browser's back/forward buttons for in-page navigation by
 * adding custom 'next' and 'previous' events to the window object.
 *
 * Copyright (c) 2011 Tobias Schneider <schneider@jancona.com>
 * This script is freely distributable under the terms of the MIT license.
 *
 * Example:
 *
 *  window.addEventListener('next', function(){
 *    console.log('forward button clicked');
 *  }, false);
 *
 *  window.addEventListener('previous', function(){
 *    console.log('back button clicked');
 *  }, false);
 */

if(window.history && history.pushState){ // check for history api support
  window.addEventListener('load', function(){
    // create history states
    history.pushState(-1, null); // back state
    history.pushState(0, null); // main state
    history.pushState(1, null); // forward state
    history.go(-1); // start in main state
        
    this.addEventListener('popstate', function(event, state){
      // check history state and fire custom events
      if(state = event.state){
  
        event = document.createEvent('Event');
        event.initEvent(state > 0 ? 'next' : 'previous', true, true);
        this.dispatchEvent(event);
        
        // reset state
        history.go(-state);
      }
    }, false);
  }, false);
}