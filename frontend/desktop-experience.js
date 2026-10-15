'use strict';
let desktopPreferences={layout:'fit',contrast:false,reduce_motion:false};
function applyDesktopPreferences(value){desktopPreferences={...value};document.documentElement.dataset.layout=value.layout;document.documentElement.classList.toggle('strong-contrast',value.contrast);document.documentElement.classList.toggle('reduced-motion',value.reduce_motion);$('desktop-layout').value=value.layout;$('desktop-contrast').checked=value.contrast;$('desktop-motion').checked=value.reduce_motion;scaleUI();}
async function loadDesktopPreferences(){try{applyDesktopPreferences(await call('desktop_preferences'));}catch(error){$('desktop-save-status').textContent='Could not load display settings: '+error.message;}}
let desktopReturnFocus=null;
function openDesktopOptions(event){if(document.querySelector('dialog[open]'))return;desktopReturnFocus=event?.currentTarget||document.activeElement;closeGuide();$('desktop-save-status').textContent='';$('desktop-dialog').showModal();$('desktop-layout').focus();}
window.closeDesktopForApproval=()=>{if($('desktop-dialog').open)$('desktop-dialog').close();};
$('desktop-options').onclick=openDesktopOptions;
$('desktop-close').onclick=()=>{$('desktop-dialog').close();if(!document.querySelector('dialog[open]')&&desktopReturnFocus?.isConnected)desktopReturnFocus.focus();};
async function saveDesktopPreferences(value){$('desktop-save').disabled=true;$('desktop-reset').disabled=true;try{applyDesktopPreferences(await call('desktop_preferences',value));$('desktop-save-status').textContent='Display settings saved.';}catch(error){$('desktop-save-status').textContent='Display settings were not saved: '+error.message;}finally{$('desktop-save').disabled=false;$('desktop-reset').disabled=false;}}
$('desktop-save').onclick=()=>saveDesktopPreferences({layout:$('desktop-layout').value,contrast:$('desktop-contrast').checked,reduce_motion:$('desktop-motion').checked});
$('desktop-reset').onclick=()=>saveDesktopPreferences({layout:'fit',contrast:false,reduce_motion:false});
function focusDesktopContent(){const target=activeView==='chat'?$('prompt'):$('route-title');target.focus();target.scrollIntoView({block:'nearest',inline:'nearest'});}
$('skip-content').onclick=focusDesktopContent;
function updateDesktopRoute(){const covered=activeView!=='chat';$('chat-view').setAttribute('aria-hidden',String(covered));for(const el of $('chat-view').querySelectorAll('button,input,textarea,select,[tabindex]')){if(covered){if(!el.hasAttribute('data-desktop-tab'))el.setAttribute('data-desktop-tab',el.getAttribute('tabindex')??'unset');el.tabIndex=-1;}else if(el.hasAttribute('data-desktop-tab')){const saved=el.getAttribute('data-desktop-tab');if(saved==='unset')el.removeAttribute('tabindex');else el.setAttribute('tabindex',saved);el.removeAttribute('data-desktop-tab');}}for(const nav of document.querySelectorAll('nav[aria-label="Main navigation"] button')){if(nav.classList.contains('active')||nav.dataset.view===activeView)nav.setAttribute('aria-current','page');else nav.removeAttribute('aria-current');}focusDesktopContent();}
document.addEventListener('keydown',event=>{if(event.defaultPrevented||event.repeat||document.querySelector('dialog[open]'))return;if(event.ctrlKey&&event.altKey&&!event.shiftKey&&event.key.toLowerCase()==='a'){event.preventDefault();openDesktopOptions();return;}if(event.altKey&&!event.ctrlKey&&!event.shiftKey){const route={'1':'chat','2':'tools','3':'workspace','4':'settings'}[event.key];if(route){event.preventDefault();view(route);}}});
// Give scrollable source and result regions a keyboard entry point without live-reading their contents.
function labelDesktopRegions(){for(const el of document.querySelectorAll('pre,#memory-list,#source-list,#files-list')){if(!el.hasAttribute('tabindex'))el.tabIndex=0;if(!el.hasAttribute('aria-label'))el.setAttribute('aria-label',el.id?el.id.replace(/-/g,' '):'Source or result text');}}
const desktopObserver=new MutationObserver(labelDesktopRegions);desktopObserver.observe($('route-body'),{childList:true,subtree:true});labelDesktopRegions();
addEventListener('pywebviewready',loadDesktopPreferences);
if(window.pywebview?.api)loadDesktopPreferences();

// Modal ownership takes priority over section help and background Escape handlers.
document.addEventListener('keydown',event=>{if(!document.querySelector('dialog[open]'))return;if(event.key==='F1'||(event.altKey&&(event.ctrlKey||['1','2','3','4'].includes(event.key)))){event.preventDefault();event.stopImmediatePropagation();}else if(event.key==='Escape'&&$('desktop-dialog').open){event.stopImmediatePropagation();}},true);

$('desktop-dialog').addEventListener('close',()=>{if(!document.querySelector('dialog[open]')&&desktopReturnFocus?.isConnected)desktopReturnFocus.focus();});
