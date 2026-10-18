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
        const measured = v.bandwidth_source === 'measured-segment-windows-v1' &&
          Number.isSafeInteger(v.bandwidth) && v.bandwidth > 0 &&
          Number.isSafeInteger(v.average_bandwidth) && v.average_bandwidth > 0;
        const rate = measured ? `实测峰值 ${v.bandwidth} bps / 平均 ${v.average_bandwidth} bps${v.bandwidth_window === 'short-vod-single-segment' ? '（极短片段）' : ''}` : '码率未实测';
        const merged = v.deduplication_source === 'sha256-vod-bytes-v1' &&
          Array.isArray(v.deduplicated_profiles) ? [...new Set(v.deduplicated_profiles)]
            .filter(p => ['480','720'].includes(p) && p !== v.profile) : [];
        const dedup = merged.length ? ` · 已合并字节相同的 ${merged.join('/')} 档` : '';
        options.push({value:v.profile, label:`HLS ${v.width}×${v.height}（${v.profile} 档上限） · ${rate}${dedup}`});
      }
    } else {
      // Completed pre-migration jobs remain playable, without inventing size.
      for (const profile of ['480','720']) options.push({value:profile, label:`HLS ${profile} 档（旧任务，尺寸未记录；码率未实测）`});
    }
  }
  select.replaceChildren(...options.map(o => {
    const node = document.createElement('option');
    node.value = o.value; node.textContent = o.label; return node;
  }));
  select.value = options.some(o => o.value === selected) ? selected : 'original';
}

function updateProcessingControls(job, mine) {
  const cancel = document.querySelector('#cancel-media');
  const retry = document.querySelector('#retry-media');
  const active = ['queued','running','cancelling'].includes(job.state);
  if (cancel) {
    cancel.classList.toggle('hidden', !mine || !active);
    cancel.disabled = job.state === 'cancelling';
    cancel.textContent = job.state === 'cancelling' ? '正在取消…' : '取消转码';
  }
  if (retry) {
    retry.classList.toggle('hidden', !mine);
    retry.disabled = active;
  }
}

function processingResponseIsCurrent(id, generation, video, currentGeneration) {
  return generation === currentGeneration && video?.id === id;
}
