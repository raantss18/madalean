function e(e){return e.key!==`Enter`||e.isComposing||e.keyCode===229||e.altKey?`none`:e.shiftKey?`newline`:`submit`}function t(){return typeof matchMedia>`u`?!1:matchMedia(`(pointer: coarse)`).matches&&!matchMedia(`(any-pointer: fine)`).matches}function n(n,r){let i=r,a=n=>{e(n)===`submit`&&(!t()||n.ctrlKey||n.metaKey)&&(n.preventDefault(),n.stopPropagation(),i())};return n.addEventListener(`keydown`,a),{update(e){i=e},destroy(){n.removeEventListener(`keydown`,a)}}}var r=`    `;function i(e,t,n){let i=e.lastIndexOf(`
`,t-1)+1,a=e.slice(i,t),o=/^[ \t]*/.exec(a)[0];/:\s*$/.test(a)&&(o+=r);let s=`
`+o;return{text:e.slice(0,t)+s+e.slice(n),start:t+s.length,end:t+s.length}}function a(e,t,n,i){let a=e.lastIndexOf(`
`,t-1)+1;if(!i&&t===n)return{text:e.slice(0,t)+r+e.slice(n),start:t+4,end:t+4};let o=e.indexOf(`
`,n-+(n>t&&e[n-1]===`
`)),s=o===-1?e.length:o,c=e.slice(a,s).split(`
`),l=0,u=0,d=c.map((e,t)=>{if(i){let n=/^ {0,4}/.exec(e)[0].length||+!!e.startsWith(`	`);return t===0&&(l=-n),u-=n,e.slice(n)}return t===0&&(l=4),u+=4,r+e});return{text:e.slice(0,a)+d.join(`
`)+e.slice(s),start:Math.max(a,t+l),end:Math.max(a,n+u)}}function o(e,t){e.value=t.text,e.setSelectionRange(t.start,t.end),e.dispatchEvent(new Event(`input`,{bubbles:!0}))}export{a,i,e as n,t as o,n as r,o as t};