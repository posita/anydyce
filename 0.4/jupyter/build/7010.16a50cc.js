"use strict";(self.webpackChunk_JUPYTERLAB_CORE_OUTPUT=self.webpackChunk_JUPYTERLAB_CORE_OUTPUT||[]).push([[7010,7505],{67505:(e,t,o)=>{o.r(t),o.d(t,{default:()=>w});var n=o(94367),a=o(27476),s=o(91857),r=o(27216),l=o(54218),c=o(32421),d=o(13790),i=o(95191),u=o(61313),m=o(60150);const p="jp-RetroKernelStatus-error",k="jp-RetroKernelStatus-warn",g="jp-RetroKernelStatus-info",h="jp-RetroKernelStatus-fade",C={id:"@retrolab/notebook-extension:checkpoints",autoStart:!0,requires:[s.IDocumentManager,d.ITranslator],optional:[i.IRetroShell],activate:(e,t,o,s)=>{const{shell:r}=e,l=o.load("retrolab"),c=new m.Widget;c.id=n.DOMUtils.createDomID(),c.addClass("jp-RetroCheckpoint"),e.shell.add(c,"top",{rank:100});const d=async()=>{const e=r.currentWidget;if(!e)return;const o=t.contextForWidget(e);null==o||o.fileChanged.disconnect(d),null==o||o.fileChanged.connect(d);const n=await(null==o?void 0:o.listCheckpoints());if(!n)return;const s=n[n.length-1];c.node.textContent=l.__("Last Checkpoint: %1",a.Time.formatHuman(new Date(s.last_modified)))};s&&s.currentChanged.connect(d),new u.Poll({auto:!0,factory:()=>d(),frequency:{interval:2e3,backoff:!1},standby:"when-hidden"})}},b={id:"@retrolab/notebook-extension:kernel-logo",autoStart:!0,requires:[i.IRetroShell],activate:(e,t)=>{const{serviceManager:o}=e;let n;const a=async()=>{var s,r,c,d,i;n&&(n.dispose(),n.parent=null);const u=t.currentWidget;if(!(u instanceof l.NotebookPanel))return;await u.sessionContext.ready,u.sessionContext.kernelChanged.disconnect(a),u.sessionContext.kernelChanged.connect(a);const p=null!==(c=null===(r=null===(s=u.sessionContext.session)||void 0===s?void 0:s.kernel)||void 0===r?void 0:r.name)&&void 0!==c?c:"",k=null===(i=null===(d=o.kernelspecs)||void 0===d?void 0:d.specs)||void 0===i?void 0:i.kernelspecs[p];if(!k)return;const g=k.resources["logo-64x64"];if(!g)return;const h=document.createElement("div"),C=document.createElement("img");C.src=g,C.title=k.display_name,h.appendChild(C),n=new m.Widget({node:h}),n.addClass("jp-RetroKernelLogo"),e.shell.add(n,"top",{rank:10010})};e.started.then((()=>{t.currentChanged.connect(a)}))}},f={id:"@retrolab/notebook-extension:kernel-status",autoStart:!0,requires:[i.IRetroShell,d.ITranslator],activate:(e,t,o)=>{const n=o.load("retrolab"),s=new m.Widget;s.addClass("jp-RetroKernelStatus"),e.shell.add(s,"menu",{rank:10010});const r=e=>{const t=e.kernelDisplayStatus;let o=`Kernel ${a.Text.titleCase(t)}`;switch(s.removeClass(p),s.removeClass(k),s.removeClass(g),s.removeClass(h),t){case"busy":case"idle":o="",s.addClass(h);break;case"dead":case"terminating":s.addClass(p);break;case"unknown":s.addClass(k);break;default:s.addClass(g),s.addClass(h)}s.node.textContent=n.__(o)};t.currentChanged.connect((async()=>{const e=t.currentWidget;e instanceof l.NotebookPanel&&e.sessionContext.statusChanged.connect(r)}))}},v={id:"@retrolab/notebook-extension:menu-plugin",autoStart:!0,requires:[r.IMainMenu,d.ITranslator],activate:(e,t,o)=>{const{commands:n}=e,a=o.load("retrolab"),s=new m.Menu({commands:n});s.title.label=a._p("menu","Cell Type"),["notebook:change-cell-to-code","notebook:change-cell-to-markdown","notebook:change-cell-to-raw"].forEach((e=>{s.addItem({command:e})})),t.runMenu.addItem({type:"separator",rank:1e3}),t.runMenu.addItem({type:"submenu",submenu:s,rank:1010})}},y={id:"@retrolab/notebook-extension:scroll-output",autoStart:!0,requires:[l.INotebookTracker],optional:[c.ISettingRegistry],activate:async(e,t,o)=>{let n=!0;const a=e=>{if(!n)return;const{outputArea:t}=e;if(void 0!==e.model.metadata.get("scrolled"))return;const{node:o}=t,a=o.scrollHeight>1.3*(parseFloat(o.style.fontSize.replace("px",""))||14)*100;e.toggleClass("jp-mod-outputsScrolled",a)};if(t.widgetAdded.connect(((e,t)=>{var o;null===(o=t.model)||void 0===o||o.cells.changed.connect(((e,o)=>{if("add"!==o.type)return;const[n]=o.newValues;t.content.widgets.forEach((e=>{if(e.model.id===n.id&&"code"===e.model.type){const t=e;t.outputArea.model.changed.connect((()=>a(t)))}}))})),t.sessionContext.ready.then((()=>{t.content.widgets.forEach((e=>{"code"===e.model.type&&a(e)}))}))})),o){const t=o.load(y.id),a=e=>{n=e.get("autoScrollOutputs").composite};Promise.all([t,e.restored]).then((([e])=>{a(e),e.changed.connect((e=>{a(e)}))})).catch((e=>{console.error(e.message)}))}}},w=[C,b,f,v,{id:"@retrolab/notebook-extension:run-shortcut",autoStart:!0,activate:e=>{e.commands.addKeyBinding({command:"notebook:run-cell",keys:["Accel Enter"],selector:".jp-Notebook:focus"}),e.commands.addKeyBinding({command:"notebook:run-cell",keys:["Accel Enter"],selector:".jp-Notebook.jp-mod-editMode"})}},y]}}]);
//# sourceMappingURL=7010.16a50cc.js.map