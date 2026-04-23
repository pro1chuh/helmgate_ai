// app/ui.jsx — shared UI primitives (icons, avatar, badges)
// All icons as tiny inline-SVG React components

const ic = (d, extra={}) => (props={}) => React.createElement('svg',
  { width:16,height:16,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.8,strokeLinecap:'round',strokeLinejoin:'round',...extra,...props },
  ...(Array.isArray(d)?d:[d]).map((el,i)=>React.createElement(el.tag,{key:i,...el.p}))
);

const IconPlus      = ic([{tag:'line',p:{x1:12,y1:5,x2:12,y2:19}},{tag:'line',p:{x1:5,y1:12,x2:19,y2:12}}]);
const IconChat      = ic([{tag:'path',p:{d:'M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z'}}]);
const IconFile      = ic([{tag:'path',p:{d:'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z'}},{tag:'polyline',p:{points:'14 2 14 8 20 8'}}]);
const IconFolder    = ic([{tag:'path',p:{d:'M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z'}}]);
const IconUsers     = ic([{tag:'path',p:{d:'M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2'}},{tag:'circle',p:{cx:9,cy:7,r:4}},{tag:'path',p:{d:'M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75'}}]);
const IconShield    = ic([{tag:'path',p:{d:'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'}}]);
const IconMoon      = ic([{tag:'path',p:{d:'M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z'}}]);
const IconSun       = ic([{tag:'circle',p:{cx:12,cy:12,r:5}},{tag:'line',p:{x1:12,y1:1,x2:12,y2:3}},{tag:'line',p:{x1:12,y1:21,x2:12,y2:23}},{tag:'line',p:{x1:4.22,y1:4.22,x2:5.64,y2:5.64}},{tag:'line',p:{x1:18.36,y1:18.36,x2:19.78,y2:19.78}},{tag:'line',p:{x1:1,y1:12,x2:3,y2:12}},{tag:'line',p:{x1:21,y1:12,x2:23,y2:12}},{tag:'line',p:{x1:4.22,y1:19.78,x2:5.64,y2:18.36}},{tag:'line',p:{x1:18.36,y1:5.64,x2:19.78,y2:4.22}}]);
const IconSend      = ic([{tag:'line',p:{x1:22,y1:2,x2:11,y2:13}},{tag:'polygon',p:{points:'22 2 15 22 11 13 2 9 22 2'}}],{strokeWidth:2.2});
const IconPaperclip = ic([{tag:'path',p:{d:'M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48'}}]);
const IconMic       = ic([{tag:'path',p:{d:'M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z'}},{tag:'path',p:{d:'M19 10v2a7 7 0 01-14 0v-2'}},{tag:'line',p:{x1:12,y1:19,x2:12,y2:23}},{tag:'line',p:{x1:8,y1:23,x2:16,y2:23}}]);
const IconCopy      = ic([{tag:'rect',p:{x:9,y:9,width:13,height:13,rx:2}},{tag:'path',p:{d:'M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1'}}],{width:14,height:14});
const IconCheck     = ic([{tag:'polyline',p:{points:'20 6 9 17 4 12'}}],{strokeWidth:2.5,width:14,height:14});
const IconLogout    = ic([{tag:'path',p:{d:'M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4'}},{tag:'polyline',p:{points:'16 17 21 12 16 7'}},{tag:'line',p:{x1:21,y1:12,x2:9,y2:12}}]);
const IconBrain     = ic([{tag:'path',p:{d:'M9.5 2A2.5 2.5 0 007 4.5v0A2.5 2.5 0 004.5 7v0A2.5 2.5 0 002 9.5v5A2.5 2.5 0 004.5 17v0A2.5 2.5 0 007 19.5v0A2.5 2.5 0 009.5 22h5a2.5 2.5 0 002.5-2.5v0a2.5 2.5 0 002.5-2.5v0A2.5 2.5 0 0022 14.5v-5A2.5 2.5 0 0019.5 7v0A2.5 2.5 0 0017 4.5v0A2.5 2.5 0 0014.5 2z'}}],{width:14,height:14});
const IconSearch    = ic([{tag:'circle',p:{cx:11,cy:11,r:8}},{tag:'line',p:{x1:21,y1:21,x2:16.65,y2:16.65}}],{width:14,height:14});
const IconUpload    = ic([{tag:'polyline',p:{points:'16 16 12 12 8 16'}},{tag:'line',p:{x1:12,y1:12,x2:12,y2:21}},{tag:'path',p:{d:'M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3'}}],{width:20,height:20});
const IconTrash     = ic([{tag:'polyline',p:{points:'3 6 5 6 21 6'}},{tag:'path',p:{d:'M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6'}},{tag:'path',p:{d:'M10 11v6M14 11v6'}},{tag:'path',p:{d:'M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2'}}],{width:14,height:14});
const IconDots      = (props={}) => React.createElement('svg',{width:14,height:14,viewBox:'0 0 24 24',fill:'currentColor',...props},
  React.createElement('circle',{cx:12,cy:5,r:1.5}),
  React.createElement('circle',{cx:12,cy:12,r:1.5}),
  React.createElement('circle',{cx:12,cy:19,r:1.5})
);
const IconChevron = ({ dir='down', size=13 }) => {
  const pts = { down:'6 9 12 15 18 9', up:'18 15 12 9 6 15', right:'9 18 15 12 9 6', left:'15 6 9 12 15 18' };
  return React.createElement('svg',{width:size,height:size,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:2,strokeLinecap:'round'},
    React.createElement('polyline',{points:pts[dir]}));
};
const IconStar = ic([{tag:'polygon',p:{points:'12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'}}]);
const IconX = ic([{tag:'line',p:{x1:18,y1:6,x2:6,y2:18}},{tag:'line',p:{x1:6,y1:6,x2:18,y2:18}}],{strokeWidth:2.5});

// ── Avatar ────────────────────────────────────────────────────────────────
function Avatar({ name='?', size=32, color='#6366F1', style:extraStyle={} }) {
  return React.createElement('div', {
    style:{ width:size, height:size, borderRadius:'50%', background:color, color:'#fff',
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize:size*0.38, fontWeight:700, flexShrink:0, userSelect:'none',
      letterSpacing:'-0.5px', ...extraStyle }
  }, name.charAt(0).toUpperCase());
}

// ── ModelBadge ────────────────────────────────────────────────────────────
function ModelBadge({ model, taskType }) {
  const styles = {
    code:     { bg:'rgba(245,158,11,.13)', color:'#B45309' },
    analysis: { bg:'rgba(139,92,246,.13)', color:'#6D28D9' },
    text:     { bg:'rgba(99,102,241,.11)', color:'#4338CA' },
    default:  { bg:'rgba(99,102,241,.11)', color:'#4338CA' },
  };
  const s = styles[taskType] || styles.default;
  return React.createElement('span', {
    style:{ display:'inline-block', fontSize:10.5, fontWeight:700,
      background:s.bg, color:s.color, padding:'2px 8px',
      borderRadius:5, letterSpacing:'.3px', fontFamily:'inherit' }
  }, model);
}

// ── Spinner ───────────────────────────────────────────────────────────────
function Spinner({ size=15 }) {
  return React.createElement('span', { className:'spinner', style:{ width:size, height:size } });
}

// ── FileIcon ──────────────────────────────────────────────────────────────
function FileTypeIcon({ ext }) {
  const colors = { pdf:'#EF4444', xlsx:'#10B981', docx:'#3B82F6', txt:'#6B7280' };
  const c = colors[ext] || '#6B7280';
  return React.createElement('div', {
    style:{ width:38, height:38, borderRadius:9, background:c+'1a', color:c,
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize:11, fontWeight:800, flexShrink:0, letterSpacing:'.3px' }
  }, (ext||'file').toUpperCase());
}

Object.assign(window, {
  Avatar, ModelBadge, Spinner, FileTypeIcon,
  IconPlus, IconChat, IconFile, IconFolder, IconUsers, IconShield, IconMoon, IconSun,
  IconSend, IconPaperclip, IconMic, IconCopy, IconCheck, IconLogout, IconBrain,
  IconSearch, IconUpload, IconTrash, IconDots, IconChevron, IconStar, IconX,
});
