// Use encoded dimensions, not the profile's height ceiling, as quality labels.
function updateMediaProfiles(job) {
  const select = document.querySelector('[aria-label="播放模式"]');
  if (!select) return;
  const selected = select.value;
  const options = [{value:'original', label:'原视频'}];
  if (job.state === 'completed') {
    options.push({value:'auto', label:'HLS 自动码率'});
    const variants = job.variants || [];
    if (variants.length) {
      for (const v of variants) {
        if (!['480','720'].includes(v.profile) || !Number.isInteger(v.width) || !Number.isInteger(v.height)) continue;
        options.push({value:v.profile, label:`HLS ${v.width}×${v.height}（${v.profile} 档上限）`});
      }
    } else {
      // Completed pre-migration jobs remain playable, without inventing size.
      for (const profile of ['480','720']) options.push({value:profile, label:`HLS ${profile} 档（旧任务，尺寸未记录）`});
    }
  }
  select.replaceChildren(...options.map(o => {
    const node = document.createElement('option');
    node.value = o.value; node.textContent = o.label; return node;
  }));
  select.value = options.some(o => o.value === selected) ? selected : 'original';
}
