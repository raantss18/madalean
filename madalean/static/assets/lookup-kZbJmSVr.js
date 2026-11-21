import{c as e}from"./index-IYDNwGoc.js";var t=new Map;function n(n,r){let i=`${r??``}|${n}`,a=t.get(i);return a||(a=e.learnToken(n,r).then(e=>{if(e.known===!1)return null;let t=[e.signature,e.doc||e.text].filter(Boolean).join(`

`);return t?{title:String(e.name??n),body:t,module:e.module}:null}).catch(()=>null),t.set(i,a)),a}export{n as lookupToken};