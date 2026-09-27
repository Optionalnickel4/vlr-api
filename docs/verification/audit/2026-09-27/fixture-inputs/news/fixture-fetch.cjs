const fs=require('node:fs');const original=globalThis.fetch;
globalThis.fetch=async function(input,options){const url=String(input?.url??input);if(url==='http://127.0.0.1:8101/api/v1/news'){
 const kind=fs.readFileSync('/tmp/vlr-news-delivery/scenario','utf8').trim();if(kind==='error')return new Response('{}',{status:503});if(kind==='empty')return Response.json([]);
 return Response.json([{title:'CONTROLLED · '+ 'LongHeadline'.repeat(10),description:'CONTROLLED excerpt intentionally omitted from the news page.',meta:'•Supplied date text•by Controlled author',url:'https://www.vlr.gg/controlled-news-1'},{title:null,description:null,meta:null,url:null},{title:'CONTROLLED · Final supplied story',description:null,meta:'•January 1, 2000•by Controlled reporter',url:'https://www.vlr.gg/controlled-news-3'}]);
}return original(input,options);};
