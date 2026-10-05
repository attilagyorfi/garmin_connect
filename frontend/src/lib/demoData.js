export const heat = [1,2,1,0,2,2,3,1,2,3,2,1,3,2,2,1,0,2,3,1,2,3,3,2,1,2,3,2,0,1,2,3,2,1,0,2,3,2,3,1,2,3,2,3,1,2,3,2,3,3,2,1,3,2,2,3,1,2,3,2,1,3,2,3,3,2,1,2,3,3,0,1,2,1,2,3,2,1,3,2,2,3,1,2];
export const metrics = [["HRV (éjszakai)","62 ms","+5%",68,"warn"],["Alvás","7ó 12p","+6%",76,"good"],["Nyugalmi pulzus","48 bpm","−3",82,"good"],["Hibrid TSB","+4,2","+2,1",61,"good"]];
export const trendData=Array.from({length:12},(_,i)=>({week:`${i+1}. hét`,ctl:32+i*1.8+(i%3),atl:30+i*2+(i%2?6:-2),tsb:5+(i%4)*1.4}));
