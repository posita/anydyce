"use strict";(self.webpackChunk_JUPYTERLAB_CORE_OUTPUT=self.webpackChunk_JUPYTERLAB_CORE_OUTPUT||[]).push([[143],{143:(e,t,s)=>{s.r(t),s.d(t,{CodeMirrorSearchProvider:()=>o,FOUND_CLASSES:()=>u,GenericSearchProvider:()=>_,ISearchProviderRegistry:()=>U,NotebookSearchProvider:()=>v,SearchInstance:()=>q,SearchProviderRegistry:()=>B,SearchState:()=>l});var r=s(12120),i=s(91981),n=s(27485),a=s(58646),c=s(41981),h=s.n(c);class o{constructor(){this.isReadOnly=!1,this.isSubProvider=!1,this._matchState={},this._changed=new a.Signal(this)}getInitialQuery(e){const t=e.content.editor.doc.getSelection();return-1===t.search(/\r?\n|\r/g)?t:""}async startQuery(e,t,s={}){if(!o.canSearchOn(t))throw new Error("Cannot find Codemirror instance to search");return this._cm=t.content.editor,this._startQuery(e)}async startQueryCodeMirror(e,t){return this._cm=t,this._startQuery(e,!1)}refreshOverlay(){this._refreshOverlay()}async _startQuery(e,t=!0){await this.endQuery(!1),this._query=e,c.on(this._cm.doc,"change",this._onDocChanged.bind(this)),t&&this._refreshOverlay(),this._setInitialMatches(e);const s=this._parseMatchesFromState();if(0===s.length)return[];if(!this.isSubProvider){const e=this._findNext(!1),t=e&&this._matchState[e.from.line][e.from.ch];this._currentMatch=t}return s}async endQuery(e=!0){this._matchState={},this._currentMatch=null,e&&this._cm.removeOverlay(this._overlay);const t=this._cm.getCursor("from"),s=this._cm.getCursor("to");t!==s&&this._cm.setSelection({start:this._toEditorPos(s),end:this._toEditorPos(t)}),c.off(this._cm.doc,"change",this._onDocChanged.bind(this))}async endSearch(){return this.isSubProvider||this._cm.focus(),this.endQuery()}async highlightNext(){const e=this._findNext(!1);if(!e)return;const t=this._matchState[e.from.line][e.from.ch];return this._currentMatch=t,t}async highlightPrevious(){const e=this._findNext(!0);if(!e)return;const t=this._matchState[e.from.line][e.from.ch];return this._currentMatch=t,t}async replaceCurrentMatch(e){let t=!1;if(this._currentMatchIsSelected()){const s=this._cm.getSearchCursor(this._query,this._cm.getCursor("from"),!this._query.ignoreCase);if(!s.findNext())return t;t=!0,s.replace(e)}return await this.highlightNext(),t}async replaceAllMatches(e){let t=!1;return new Promise(((s,r)=>{this._cm.operation((()=>{const r=this._cm.getSearchCursor(this._query,void 0,!this._query.ignoreCase);for(;r.findNext();)t=!0,r.replace(e);this._matchState={},this._currentMatch=null,s(t)}))}))}static canSearchOn(e){return e instanceof r.MainAreaWidget&&e.content instanceof n.FileEditor&&e.content.editor instanceof i.CodeMirrorEditor}get matches(){return this._parseMatchesFromState()}get currentMatch(){return this._currentMatch}get changed(){return this._changed}get currentMatchIndex(){return this._currentMatch?this._currentMatch.index:null}clearSelection(){}get editor(){return this._cm}_onDocChanged(e,t){var s,r;(t.text.length>1||(null!==(r=null===(s=t.removed)||void 0===s?void 0:s.length)&&void 0!==r?r:0)>1)&&(this._setInitialMatches(this._query),this._changed.emit(void 0))}_refreshOverlay(){this._cm.operation((()=>{this._cm.removeOverlay(this._overlay),this._overlay=this._getSearchOverlay(),this._cm.addOverlay(this._overlay),this._changed.emit(void 0)}))}_setInitialMatches(e){this._matchState={};const t=c.Pos(this._cm.doc.firstLine(),0),s=c.Pos(this._cm.doc.lastLine());this._cm.doc.getRange(t,s).split("\n").forEach(((t,s)=>{e.lastIndex=0;let r=e.exec(t);for(;r;){const i=r.index,n={text:r[0],line:s,column:i,fragment:t,index:0};this._matchState[s]||(this._matchState[s]={}),this._matchState[s][i]=n,r=e.exec(t)}}))}_getSearchOverlay(){return{token:e=>{const t=e.pos;this._query.lastIndex=t;const s=e.string,r=this._query.exec(s),i=e.lineOracle.line;if(e.start===t&&0===t&&this._matchState[i]&&(this._matchState[i]={}),r&&r.index===t){const n=r[0].length,a={text:s.substr(t,n),line:i,column:t,fragment:s,index:0};return this._matchState[i]||(this._matchState[i]={}),this._matchState[i][t]=a,e.pos+=n||1,e.eol()&&this._changed.emit(void 0),"searching"}r?e.pos=r.index:(this._changed.emit(void 0),e.skipToEnd())}}}_findNext(e){return this._cm.operation((()=>{const t=this._query.ignoreCase,s=e?"anchor":"head",r=this._cm.getCursor(s),i=this._toEditorPos(r);let n=this._cm.getSearchCursor(this._query,r,!t);if(!n.find(e)){if(this.isSubProvider)return this._cm.setCursorPosition(i,{scroll:!1}),this._currentMatch=null,null;const s=e?c.Pos(this._cm.lastLine()):c.Pos(this._cm.firstLine(),0);if(n=this._cm.getSearchCursor(this._query,s,!t),!n.find(e))return null}const a=n.from(),h=n.to(),o={start:{line:a.line,column:a.ch},end:{line:h.line,column:h.ch}};return this._cm.setSelection(o),this._cm.scrollIntoView({from:a,to:h},100),{from:a,to:h}}))}_parseMatchesFromState(){let e=0;return Object.keys(this._matchState).reduce(((t,s)=>{const r=parseInt(s,10),i=this._matchState[r];return Object.keys(i).forEach((s=>{const r=parseInt(s,10),n=i[r];n.index=e,e+=1,t.push(n)})),t}),[])}_toEditorPos(e){return{line:e.line,column:e.ch}}_currentMatchIsSelected(){if(!this._currentMatch)return!1;const e=this._cm.getSelection(),t=e.end.column-e.start.column,s=e.start.line===e.end.line;return this._currentMatch.line===e.start.line&&this._currentMatch.column===e.start.column&&this._currentMatch.text.length===t&&s}}class l{}var d=s(28877);const u=["cm-string","cm-overlay","cm-searching"],p=["CodeMirror-selectedtext"];class _{constructor(){this.isReadOnly=!0,this.isSubProvider=!1,this._matches=[],this._mutationObserver=new MutationObserver(this._onWidgetChanged.bind(this)),this._changed=new a.Signal(this)}getInitialQuery(e){return""}async startQuery(e,t,s={}){const r=this;await this.endQuery(!1),this._widget=t,this._query=e,this._mutationObserver.disconnect();const i=[],n=document.createTreeWalker(this._widget.node,NodeFilter.SHOW_TEXT,{acceptNode:e=>{let t=e.parentElement;for(;t!==this._widget.node;){if(t.nodeName in _.UNSUPPORTED_ELEMENTS)return NodeFilter.FILTER_REJECT;t=t.parentElement}return r._query.test(e.textContent)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}},!1),a=[],c=[];let h=n.nextNode();for(;h;)a.push(h),c.push(h.parentElement.cloneNode(!0)),h=n.nextNode();const o=-1===this._query.flags.indexOf("g")?e.flags+"g":e.flags;return a.forEach(((t,s)=>{const r=new RegExp(e.source,o),n=[];let a=r.exec(t.textContent);for(;a;)n.push({start:a.index,end:a.index+a[0].length,text:a[0]}),a=r.exec(t.textContent);const h=c[s],l=t.textContent.length;let d=null;const p=[];for(let e=n.length-1;e>=0;--e){const{start:s,end:r,text:i}=n[e],a=document.createElement("span");if(a.classList.add(...u),a.textContent=i,t.textContent=`${t.textContent.slice(0,s)}${t.textContent.slice(r)}`,(null==t?void 0:t.nodeType)==Node.TEXT_NODE){const e=t.splitText(s);t.parentNode.insertBefore(a,e)}else 0===s?t.parentNode.prepend(a):r===l?t.parentNode.append(a):d&&r===n[e+1].start&&t.parentNode.insertBefore(a,d);d=a,p.unshift({text:i,fragment:"",line:0,column:0,index:-1,matchesIndex:-1,indexInOriginal:e,spanElement:a,originalNode:h})}i.push(...p)})),i.forEach(((e,t)=>{e.index=t,e.matchesIndex=t})),!this.isSubProvider&&i.length>0&&(this._currentMatch=i[0]),this._mutationObserver.observe(this._widget.node,{attributes:!1,characterData:!0,childList:!0,subtree:!0}),this._matches=i,this._matches}refreshOverlay(){}async endQuery(e=!0){this._matches.forEach((e=>{0===e.indexInOriginal&&e.spanElement.parentElement.replaceWith(e.originalNode)})),this._matches=[],this._currentMatch=null,this._mutationObserver.disconnect()}async endSearch(){return this.endQuery()}async highlightNext(){return this._highlightNext(!1)}async highlightPrevious(){return this._highlightNext(!0)}_highlightNext(e){if(0!==this._matches.length){if(this._currentMatch){this._currentMatch.spanElement.classList.remove(...p);let t=e?this._currentMatch.matchesIndex-1:this._currentMatch.matchesIndex+1;if(this.isSubProvider&&(t<0||t>=this._matches.length))return void(this._currentMatch=null);t=(t+this._matches.length)%this._matches.length,this._currentMatch=this._matches[t]}else this._currentMatch=e?this._matches[this.matches.length-1]:this._matches[0];return this._currentMatch&&(this._currentMatch.spanElement.classList.add(...p),function(e){const t=e.getBoundingClientRect();return t.top>=0&&t.bottom<=(window.innerHeight||document.documentElement.clientHeight)&&t.left>=0&&t.right<=(window.innerWidth||document.documentElement.clientWidth)}(this._currentMatch.spanElement)||this._currentMatch.spanElement.scrollIntoView(e),this._currentMatch.spanElement.focus()),this._currentMatch}}async replaceCurrentMatch(e){return Promise.resolve(!1)}async replaceAllMatches(e){return Promise.resolve(!1)}static canSearchOn(e){return e instanceof d.Widget}get matches(){return this._matches?this._matches.map((e=>Object.assign({},e))):this._matches}get changed(){return this._changed}get currentMatchIndex(){return this._currentMatch?this._currentMatch.index:null}get currentMatch(){return this._currentMatch}clearSelection(){}async _onWidgetChanged(e,t){await this.startQuery(this._query,this._widget),this._changed.emit(void 0)}}_.UNSUPPORTED_ELEMENTS={BASE:!0,HEAD:!0,LINK:!0,META:!0,STYLE:!0,TITLE:!0,BODY:!0,AREA:!0,AUDIO:!0,IMG:!0,MAP:!0,TRACK:!0,VIDEO:!0,APPLET:!0,EMBED:!0,IFRAME:!0,NOEMBED:!0,OBJECT:!0,PARAM:!0,PICTURE:!0,SOURCE:!0,CANVAS:!0,NOSCRIPT:!0,SCRIPT:!0,SVG:!0};var g=s(18491),m=s(2301),S=s(81734);class v{constructor(){this.isReadOnly=!1,this.hasOutputs=!0,this._searchProviders=[],this._unRenderedMarkdownCells=[],this._cellsWithMatches=[],this._changed=new a.Signal(this)}getInitialQuery(e){var t;const s=e.content.activeCell,r=null===(t=null==s?void 0:s.editor)||void 0===t?void 0:t.doc.getSelection();return-1===(null==r?void 0:r.search(/\r?\n|\r/g))?r:""}async startQuery(e,t,s){this._searchTarget=t;let r=this._searchTarget.content.widgets;this._filters=s&&0!==Object.entries(s).length?s:{output:!0,selectedCells:!1};const i=r.filter((e=>this._searchTarget.content.isSelectedOrActive(e)));this._filters.selectedCells&&i.length>0&&(r=i),this._searchTarget.hide();let n=0;const a=[];for(const t of r){const s=t.editor,r=new o;r.isSubProvider=!0;let i=!1;t instanceof g.MarkdownCell&&t.rendered&&(t.rendered=!1,i=!0),t.inputHidden&&(t.inputHidden=!1);const c=await r.startQueryCodeMirror(e,s);if(t instanceof g.MarkdownCell&&(0!==c.length?this._unRenderedMarkdownCells.push(t):i&&(t.rendered=!0)),0!==c.length&&(r.refreshOverlay(),this._cellsWithMatches.push(t)),c.forEach((e=>{e.index=e.index+n})),n+=c.length,r.changed.connect(this._onSearchProviderChanged,this),a.concat(c),this._searchProviders.push({cell:t,provider:r}),t instanceof g.CodeCell&&this._filters.output){const s=new _;s.isSubProvider=!0;const r=await s.startQuery(e,t.outputArea);r.map((e=>{e.index=e.index+n})),n+=r.length,a.concat(r),s.changed.connect(this._onSearchProviderChanged,this),this._searchProviders.push({cell:t,provider:s})}}return this._searchTarget.show(),this._currentMatch=await this._stepNext(this._updatedCurrentProvider(!1)),this._refreshCurrentCellEditor(),this._refreshCellsEditorsInBackground(this._cellsWithMatches),a}_refreshCellsEditorsInBackground(e,t=5){let s=0;const r=()=>{for(let r=s+t;s<r&&s<e.length;s++)e[s].editor.refresh();s<e.length&&window.setTimeout(r,0)};window.setTimeout(r,0)}_refreshCurrentCellEditor(){this._searchTarget.content.activeCell.editor.refresh()}async endQuery(){this._searchTarget.hide();const e=[];this._searchProviders.forEach((({provider:t})=>{e.push(t.endQuery()),t.changed.disconnect(this._onSearchProviderChanged,this)})),a.Signal.disconnectBetween(this._searchTarget.model.cells,this),this._searchProviders=[],this._currentProvider=null,this._unRenderedMarkdownCells.forEach((e=>{e.isDisposed||(e.rendered=!0)})),this._unRenderedMarkdownCells=[],await Promise.all(e),this._searchTarget.show(),this._refreshCurrentCellEditor(),this._refreshCellsEditorsInBackground(this._cellsWithMatches.filter((e=>!(e instanceof g.MarkdownCell)))),this._cellsWithMatches=[]}async endSearch(){this._searchTarget.hide(),a.Signal.disconnectBetween(this._searchTarget.model.cells,this);const e=this._searchTarget.content.activeCellIndex,t=[];this._searchProviders.forEach((({provider:e})=>{t.push(e.endSearch()),e.changed.disconnect(this._onSearchProviderChanged,this)})),this._searchProviders=[],this._currentProvider=null,this._unRenderedMarkdownCells.forEach((e=>{e.rendered=!0})),this._unRenderedMarkdownCells=[],this._searchTarget.content.activeCellIndex=e,this._searchTarget.content.mode="edit",this._currentMatch=null,await Promise.all(t),this._searchTarget.show(),this._refreshCurrentCellEditor(),this._searchTarget=null,this._refreshCellsEditorsInBackground(this._cellsWithMatches.filter((e=>!(e instanceof g.MarkdownCell)))),this._cellsWithMatches=[]}async highlightNext(){return this._currentMatch=await this._stepNext(this._updatedCurrentProvider(!1)),this._currentMatch}async highlightPrevious(){return this._currentMatch=await this._stepNext(this._updatedCurrentProvider(!0),!0),this._currentMatch}async replaceCurrentMatch(e){const t=this._searchTarget.content.activeCell.editor;let s=!1;if(this._currentMatchIsSelected(t)){const{provider:t}=this._currentProvider;if(s=await t.replaceCurrentMatch(e),s&&(this._currentMatch=t.currentMatch,this._currentMatch))return s}return await this.highlightNext(),s}async replaceAllMatches(e){let t=!1;for(const s in this._searchProviders){const{provider:r}=this._searchProviders[s];t=!!await r.replaceAllMatches(e)||t}return this._currentMatch=null,t}static canSearchOn(e){return e instanceof m.NotebookPanel}get matches(){return[].concat(...this._getMatchesFromCells())}get changed(){return this._changed}get currentMatchIndex(){return this._currentMatch?this._currentMatch.index:null}_updatedCurrentProvider(e){if(this._currentProvider&&this._currentProvider.cell===this._searchTarget.content.activeCell)return this._currentProvider;let t;if(this._currentProvider){const s=S.ArrayExt.firstIndexOf(this._searchProviders,this._currentProvider),r=((e?s-1:s+1)+this._searchProviders.length)%this._searchProviders.length;t=this._searchProviders[r]}else t=(e?S.ArrayExt.findLastValue:S.ArrayExt.findFirstValue)(this._searchProviders,(e=>this._searchTarget.content.activeCell===e.cell));return this._currentProvider=t,t}async _stepNext(e,t=!1,s=0){const{provider:r}=e,i=t?await r.highlightPrevious():await r.highlightNext();if(!i){const r=this._searchProviders.indexOf(e),i=this._searchProviders.length;if(s===i)return;const n=((t?r-1:r+1)+i)%i,a=this._searchProviders[n];if(a.provider instanceof o){const e=a.provider.editor,s=t?h().Pos(e.lastLine()):h().Pos(e.firstLine(),0),r={line:s.line,column:s.ch};e.setCursorPosition(r,{scroll:!1})}return this._currentProvider=a,this._stepNext(a,t,s+1)}const n=this._searchTarget.content;return n.activeCellIndex=n.widgets.indexOf(e.cell),i}_getMatchesFromCells(){let e=0;const t=[];return this._searchProviders.forEach((({provider:s})=>{const r=s.matches;r.forEach((t=>{t.index=t.index+e})),e+=r.length,t.push(r)})),t}_onSearchProviderChanged(){this._changed.emit(void 0)}_currentMatchIsSelected(e){if(!this._currentMatch)return!1;const t=e.getSelection(),s=t.end.column-t.start.column,r=t.start.line===t.end.line;return this._currentMatch.line===t.start.line&&this._currentMatch.column===t.start.column&&this._currentMatch.text.length===s&&r}}var y=s(55331),f=s(68465),x=s(61313),C=s(62471);const E="jp-DocumentSearch-overlay-row",M="jp-DocumentSearch-input-button-off",P="jp-DocumentSearch-input-button-on",w="jp-DocumentSearch-up-down-button",T="jp-DocumentSearch-search-options-disabled",b="jp-DocumentSearch-replace-button",I="jp-DocumentSearch-replace-button-wrapper",R="jp-DocumentSearch-button-content",O="jp-DocumentSearch-button-wrapper";class N extends C.Component{constructor(e){super(e),this.translator=e.translator||y.nullTranslator,this._trans=this.translator.load("jupyterlab"),this.searchInputRef=C.createRef()}focusInput(){var e;null===(e=this.searchInputRef.current)||void 0===e||e.select()}componentDidUpdate(){this.props.forceFocus&&this.focusInput()}render(){const e=(0,f.classes)(this.props.caseSensitive?P:M,R),t=(0,f.classes)(this.props.useRegex?P:M,R),s="jp-DocumentSearch-input-wrapper "+(this.props.inputFocused?"jp-DocumentSearch-focused-input":"");return C.createElement("div",{className:s},C.createElement("input",{placeholder:this.props.searchText?void 0:this._trans.__("Find"),className:"jp-DocumentSearch-input",value:this.props.searchText,onChange:e=>this.props.onChange(e),onKeyDown:e=>this.props.onKeydown(e),tabIndex:0,onFocus:e=>this.props.onInputFocus(),onBlur:e=>this.props.onInputBlur(),ref:this.searchInputRef}),C.createElement("button",{className:O,onClick:()=>this.props.onCaseSensitiveToggled(),tabIndex:0},C.createElement(f.caseSensitiveIcon.react,{className:e,tag:"span"})),C.createElement("button",{className:O,onClick:()=>this.props.onRegexToggled(),tabIndex:0},C.createElement(f.regexIcon.react,{className:t,tag:"span"})))}}class D extends C.Component{constructor(e){super(e),this._trans=(e.translator||y.nullTranslator).load("jupyterlab"),this.replaceInputRef=C.createRef()}render(){return C.createElement("div",{className:"jp-DocumentSearch-replace-wrapper-class"},C.createElement("input",{placeholder:this.props.replaceText?void 0:this._trans.__("Replace"),className:"jp-DocumentSearch-replace-entry",value:this.props.replaceText,onKeyDown:e=>this.props.onReplaceKeydown(e),onChange:e=>this.props.onChange(e),tabIndex:0,ref:this.replaceInputRef}),C.createElement("button",{className:I,onClick:()=>this.props.onReplaceCurrent(),tabIndex:0},C.createElement("span",{className:`${b} ${R}`,tabIndex:0},this._trans.__("Replace"))),C.createElement("button",{className:I,tabIndex:0,onClick:()=>this.props.onReplaceAll()},C.createElement("span",{className:`${b} ${R}`,tabIndex:-1},this._trans.__("Replace All"))))}}function k(e){return C.createElement("div",{className:"jp-DocumentSearch-up-down-wrapper"},C.createElement("button",{className:O,onClick:()=>e.onHighlightPrevious(),tabIndex:0},C.createElement(f.caretUpEmptyThinIcon.react,{className:(0,f.classes)(w,R),tag:"span"})),C.createElement("button",{className:O,onClick:()=>e.onHighlightNext(),tabIndex:0},C.createElement(f.caretDownEmptyThinIcon.react,{className:(0,f.classes)(w,R),tag:"span"})))}function j(e){return C.createElement("div",{className:"jp-DocumentSearch-index-counter"},0===e.totalMatches?"-/-":`${null===e.currentIndex?"-":e.currentIndex+1}/${e.totalMatches}`)}class F extends C.Component{render(){let e=`jp-DocumentSearch-ellipses-button ${R}`;return this.props.enabled&&(e=`${e} jp-DocumentSearch-ellipses-button-enabled`),C.createElement("button",{className:O,onClick:()=>this.props.toggleEnabled(),tabIndex:0},C.createElement(f.ellipsesIcon.react,{className:e,tag:"span",height:"20px",width:"20px"}))}}class A extends C.Component{render(){return C.createElement("label",{className:"jp-DocumentSearch-search-options"},C.createElement("div",null,C.createElement("span",{className:this.props.canToggleOutput?"":T},this.props.trans.__("Search Cell Outputs")),C.createElement("input",{type:"checkbox",disabled:!this.props.canToggleOutput,checked:this.props.searchOutput,onChange:this.props.toggleOutput})),C.createElement("div",null,C.createElement("span",{className:this.props.canToggleSelectedCells?"":T},this.props.trans.__("Search Selected Cell(s)")),C.createElement("input",{type:"checkbox",disabled:!this.props.canToggleSelectedCells,checked:this.props.searchSelectedCells,onChange:this.props.toggleSelectedCells})))}}class Q extends C.Component{constructor(e){var t;super(e),this.translator=e.translator||y.nullTranslator,this.state=e.overlayState,this.replaceEntryRef=C.createRef(),this._debouncedStartSearch=new x.Debouncer((()=>{this._executeSearch(!0,this.state.searchText)}),null!==(t=e.searchDebounceTime)&&void 0!==t?t:500),this._toggleSearchOutput=this._toggleSearchOutput.bind(this),this._toggleSearchSelectedCells=this._toggleSearchSelectedCells.bind(this)}componentDidMount(){this.state.searchText&&this._executeSearch(!0,this.state.searchText)}_onSearchChange(e){const t=e.target.value;this.setState({searchText:t}),this._debouncedStartSearch.invoke()}_onReplaceChange(e){this.setState({replaceText:e.target.value})}_onSearchKeydown(e){13===e.keyCode?(e.preventDefault(),e.stopPropagation(),this._executeSearch(!e.shiftKey)):27===e.keyCode&&(e.preventDefault(),e.stopPropagation(),this._onClose())}_onReplaceKeydown(e){13===e.keyCode&&(e.preventDefault(),e.stopPropagation(),this.props.onReplaceCurrent(this.state.replaceText))}_executeSearch(e,t,s=!1){let r;const i=t||this.state.searchText;try{r=W.parseQuery(i,this.props.overlayState.caseSensitive,this.props.overlayState.useRegex),this.setState({errorMessage:""})}catch(e){return void this.setState({errorMessage:e.message})}!W.regexEqual(this.props.overlayState.query,r)||s?this.props.onStartQuery(r,this.state.filters):e?this.props.onHighlightNext():this.props.onHighlightPrevious()}_onClose(){this.props.onEndSearch(),this._debouncedStartSearch.dispose()}_onReplaceToggled(){this.setState({replaceEntryShown:!this.state.replaceEntryShown})}_onSearchInputFocus(){this.state.searchInputFocused||this.setState({searchInputFocused:!0})}_onSearchInputBlur(){this.state.searchInputFocused&&this.setState({searchInputFocused:!1})}_toggleSearchOutput(){this.setState((e=>Object.assign(Object.assign({},e),{filters:Object.assign(Object.assign({},e.filters),{output:!e.filters.output})})),(()=>this._executeSearch(!0,void 0,!0)))}_toggleSearchSelectedCells(){this.setState((e=>Object.assign(Object.assign({},e),{filters:Object.assign(Object.assign({},e.filters),{selectedCells:!e.filters.selectedCells})})),(()=>this._executeSearch(!0,void 0,!0)))}_toggleFiltersOpen(){this.setState((e=>({filtersOpen:!e.filtersOpen})))}render(){const e=!this.props.isReadOnly&&this.state.replaceEntryShown,t=this.props.hasOutputs,s=t?C.createElement(F,{enabled:this.state.filtersOpen,toggleEnabled:()=>this._toggleFiltersOpen()}):null,r=t?C.createElement(A,{key:"filter",canToggleOutput:!e,canToggleSelectedCells:!0,searchOutput:this.state.filters.output,searchSelectedCells:this.state.filters.selectedCells,toggleOutput:this._toggleSearchOutput,toggleSelectedCells:this._toggleSearchSelectedCells,trans:this.translator.load("jupyterlab")}):null,i=this.state.replaceEntryShown?f.caretDownIcon:f.caretRightIcon;return[C.createElement("div",{className:E,key:0},this.props.isReadOnly?C.createElement("div",{className:"jp-DocumentSearch-toggle-placeholder"}):C.createElement("button",{className:"jp-DocumentSearch-toggle-wrapper",onClick:()=>this._onReplaceToggled(),tabIndex:0},C.createElement(i.react,{className:`jp-DocumentSearch-replace-toggle ${R}`,tag:"span",elementPosition:"center",height:"20px",width:"20px"})),C.createElement(N,{useRegex:this.props.overlayState.useRegex,caseSensitive:this.props.overlayState.caseSensitive,onCaseSensitiveToggled:()=>{this.props.onCaseSensitiveToggled(),this._executeSearch(!0)},onRegexToggled:()=>{this.props.onRegexToggled(),this._executeSearch(!0)},onKeydown:e=>this._onSearchKeydown(e),onChange:e=>this._onSearchChange(e),onInputFocus:this._onSearchInputFocus.bind(this),onInputBlur:this._onSearchInputBlur.bind(this),inputFocused:this.state.searchInputFocused,searchText:this.state.searchText,forceFocus:this.props.overlayState.forceFocus,translator:this.translator}),C.createElement(j,{currentIndex:this.props.overlayState.currentIndex,totalMatches:this.props.overlayState.totalMatches}),C.createElement(k,{onHighlightPrevious:()=>this._executeSearch(!1),onHighlightNext:()=>this._executeSearch(!0)}),e?null:s,C.createElement("button",{className:O,onClick:()=>this._onClose(),tabIndex:0},C.createElement(f.closeIcon.react,{className:"jp-icon-hover",elementPosition:"center",height:"16px",width:"16px"}))),C.createElement("div",{className:E,key:1},e?C.createElement(C.Fragment,null,C.createElement(D,{onReplaceKeydown:e=>this._onReplaceKeydown(e),onChange:e=>this._onReplaceChange(e),onReplaceCurrent:()=>this.props.onReplaceCurrent(this.state.replaceText),onReplaceAll:()=>this.props.onReplaceAll(this.state.replaceText),replaceText:this.state.replaceText,ref:this.replaceEntryRef,translator:this.translator}),C.createElement("div",{className:"jp-DocumentSearch-spacer"}),s):null),this.state.filtersOpen?r:null,C.createElement("div",{className:"jp-DocumentSearch-regex-error",hidden:!!this.state.errorMessage&&0===this.state.errorMessage.length,key:3},this.state.errorMessage),C.createElement("div",{className:"jp-DocumentSearch-document-loading",key:4},"This document is still loading. Only loaded content will appear in search results until the entire document loads.")]}}var W;!function(e){e.parseQuery=function(e,t,s){const r=t?"g":"gi",i=s?e:e.replace(/[-[\]/{}()*+?.\\^$|]/g,"\\$&");let n;return n=new RegExp(i,r),n.test("")&&(n=/x^/),n},e.regexEqual=function(e,t){return!(!e||!t)&&e.source===t.source&&e.global===t.global&&e.ignoreCase===t.ignoreCase&&e.multiline===t.multiline}}(W||(W={}));class q{constructor(e,t,s,i=500){this._displayState={currentIndex:0,totalMatches:0,caseSensitive:!1,useRegex:!1,searchText:"",query:null,errorMessage:"",searchInputFocused:!0,replaceInputFocused:!1,forceFocus:!0,replaceText:"",replaceEntryShown:!1,filters:{output:!0,selectedCells:!1},filtersOpen:!1},this._displayUpdateSignal=new a.Signal(this),this._isDisposed=!1,this._disposed=new a.Signal(this),this.translator=s||y.nullTranslator,this._widget=e,this._activeProvider=t;const n=this._activeProvider.getInitialQuery(this._widget);this._displayState.searchText=n||"",this._searchWidget=function(e){const{widgetChanged:t,overlayState:s,onCaseSensitiveToggled:i,onRegexToggled:n,onHighlightNext:a,onHighlightPrevious:c,onStartQuery:h,onReplaceCurrent:o,onReplaceAll:l,onEndSearch:d,isReadOnly:u,hasOutputs:p,searchDebounceTime:_,translator:g}=e,m=r.ReactWidget.create(C.createElement(r.UseSignal,{signal:t,initialArgs:s},((e,t)=>C.createElement(Q,{onCaseSensitiveToggled:i,onRegexToggled:n,onHighlightNext:a,onHighlightPrevious:c,onStartQuery:h,onEndSearch:d,onReplaceCurrent:o,onReplaceAll:l,overlayState:t,isReadOnly:u,hasOutputs:p,searchDebounceTime:_,translator:g}))));return m.addClass("jp-DocumentSearch-overlay"),m}({widgetChanged:this._displayUpdateSignal,overlayState:this._displayState,onCaseSensitiveToggled:this._onCaseSensitiveToggled.bind(this),onRegexToggled:this._onRegexToggled.bind(this),onHighlightNext:this._highlightNext.bind(this),onHighlightPrevious:this._highlightPrevious.bind(this),onStartQuery:this._startQuery.bind(this),onReplaceCurrent:this._replaceCurrent.bind(this),onReplaceAll:this._replaceAll.bind(this),onEndSearch:this.dispose.bind(this),isReadOnly:this._activeProvider.isReadOnly,hasOutputs:this._activeProvider.hasOutputs||!1,searchDebounceTime:i,translator:this.translator}),this._widget.disposed.connect((()=>{this.dispose()})),this._searchWidget.disposed.connect((()=>{this._widget.activate(),this.dispose()})),this._widget instanceof r.MainAreaWidget&&(this._searchWidget.node.style.top=`${this._widget.toolbar.node.clientHeight}px`),this._widget instanceof m.NotebookPanel&&this._widget.content.activeCellChanged.connect((()=>{this._displayState.query&&this._displayState.filters.selectedCells&&this._startQuery(this._displayState.query,this._displayState.filters)})),this._displaySearchWidget()}get searchWidget(){return this._searchWidget}get provider(){return this._activeProvider}focusInput(){this._displayState.forceFocus=!0,this._displayState.searchInputFocused=!0,this._displayUpdateSignal.emit(this._displayState),this._displayState.forceFocus=!1}setSearchText(e){this._displayState.searchText=e}setReplaceText(e){this._displayState.replaceText=e}showReplace(){this._displayState.replaceEntryShown=!0}updateIndices(){this._displayState.totalMatches=this._activeProvider.matches.length,this._displayState.currentIndex=this._activeProvider.currentMatchIndex,this._updateDisplay()}_updateDisplay(){this._displayState.forceFocus=!1,this._displayUpdateSignal.emit(this._displayState)}async _startQuery(e,t){this._activeProvider&&this._displayState.query&&await this._activeProvider.endQuery(),this._displayState.query=e,this._displayState.filters=t,await this._activeProvider.startQuery(e,this._widget,t),this.updateIndices(),this._activeProvider.changed.connect(this.updateIndices,this)}async _replaceCurrent(e){this._activeProvider&&this._displayState.query&&(await this._activeProvider.replaceCurrentMatch(e),this.updateIndices())}async _replaceAll(e){this._activeProvider&&this._displayState.query&&(await this._activeProvider.replaceAllMatches(e),this.updateIndices())}dispose(){this.isDisposed||(this._isDisposed=!0,this._displayState.query&&this._activeProvider.endSearch(),this._searchWidget.dispose(),this._disposed.emit(void 0),a.Signal.clearData(this))}get isDisposed(){return this._isDisposed}get disposed(){return this._disposed}_displaySearchWidget(){this._searchWidget.isAttached||d.Widget.attach(this._searchWidget,this._widget.node)}async _highlightNext(){this._displayState.query&&(await this._activeProvider.highlightNext(),this.updateIndices())}async _highlightPrevious(){this._displayState.query&&(await this._activeProvider.highlightPrevious(),this.updateIndices())}_onCaseSensitiveToggled(){this._displayState.caseSensitive=!this._displayState.caseSensitive,this._updateDisplay()}_onRegexToggled(){this._displayState.useRegex=!this._displayState.useRegex,this._updateDisplay()}}var L=s(18108);class B{constructor(){this._changed=new a.Signal(this),this._providerMap=new Map}register(e,t){return this._providerMap.set(e,t),this._changed.emit(),new L.DisposableDelegate((()=>{this._providerMap.delete(e),this._changed.emit()}))}getProviderForWidget(e){return this._findMatchingProvider(this._providerMap,e)}get changed(){return this._changed}_findMatchingProvider(e,t){for(const s of e.values())if(s.canSearchOn(t))return new s}}const U=new(s(74547).Token)("@jupyterlab/documentsearch:ISearchProviderRegistry")}}]);
//# sourceMappingURL=143.f2e1806.js.map