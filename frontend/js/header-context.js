(function attachHeaderContextHelpers() {
  function truncateText(value, maxLength) {
    const safe = typeof value === 'string' ? value.trim() : '';
    if (!safe) {
      return '';
    }
    if (safe.length <= maxLength) {
      return safe;
    }
    return `${safe.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
  }

  function pickLatestTimestamp(values) {
    const timestamps = (values || [])
      .filter(Boolean)
      .map(value => new Date(value))
      .filter(date => !Number.isNaN(date.getTime()))
      .sort((left, right) => right.getTime() - left.getTime());

    return timestamps[0] || null;
  }

  function formatRelative(value, t) {
    const latest = pickLatestTimestamp([value]);
    if (!latest) {
      return t('headerMetricNone');
    }
    if (typeof window.timeAgo === 'function') {
      return window.timeAgo(latest.toISOString());
    }
    return latest.toLocaleString();
  }

  function getSelectedChannel(channels, selectedChannelId, selectedChannelYtId) {
    return (channels || []).find(channel => (
      (selectedChannelId !== null && String(channel.id) === String(selectedChannelId))
      || (selectedChannelYtId && channel.yt_channel_id === selectedChannelYtId)
    )) || null;
  }

  function buildGlobalContext(channels, settings, t) {
    const list = Array.isArray(channels) ? channels : [];
    const unwatchedTotal = list.reduce(
      (sum, channel) => sum + Number(channel.unwatched_total || 0),
      0
    );
    const unclassifiedTotal = list.filter(channel => !(channel.category && channel.category.category)).length;
    const latest = pickLatestTimestamp([
      settings && settings.last_schedule_run_at,
      ...list.map(channel => channel.last_checked_at || channel.last_refreshed_at)
    ]);

    return {
      eyebrow: t('headerContextOverviewEyebrow'),
      title: t('headerContextOverviewTitle'),
      description: list.length
        ? t('headerContextOverviewDescription', { count: list.length })
        : t('headerContextOverviewEmpty'),
      media: null,
      metrics: [
        { label: t('headerMetricSubscriptions'), value: String(list.length) },
        { label: t('headerMetricUnwatched'), value: String(unwatchedTotal) },
        {
          label: t('headerMetricUpdated'),
          value: latest ? formatRelative(latest.toISOString(), t) : t('headerMetricNone')
        },
        { label: t('headerMetricUnclassified'), value: String(unclassifiedTotal) }
      ]
    };
  }

  function buildSelectedChannelContext(channel, t) {
    const category = channel && channel.category && channel.category.category
      ? channel.category.category
      : null;
    const lastSignal = channel
      ? channel.last_checked_at || channel.last_refreshed_at || channel.latest_video_at
      : null;

    return {
      eyebrow: t('headerContextChannelEyebrow'),
      title: channel && channel.title ? channel.title : t('unknownChannel'),
      description: truncateText(
        channel && channel.description
          ? channel.description
          : t('headerContextChannelFallback'),
        140
      ),
      media: channel && channel.thumbnail_local_url
        ? { type: 'image', url: channel.thumbnail_local_url, alt: channel.title || t('channelThumbnailAlt') }
        : null,
      metrics: [
        {
          label: t('headerMetricCategory'),
          value: category ? category.name : t('headerMetricNone')
        },
        {
          label: t('headerMetricUnwatched'),
          value: String(Number(channel && channel.unwatched_total ? channel.unwatched_total : 0))
        },
        {
          label: t('headerMetricRecent'),
          value: String(Number(channel && channel.recent_total_30 ? channel.recent_total_30 : 0))
        },
        {
          label: t('headerMetricUpdated'),
          value: lastSignal ? formatRelative(lastSignal, t) : t('headerMetricNone')
        }
      ]
    };
  }

  function buildHeaderContext(channels, selectedChannelId, selectedChannelYtId, settings, t) {
    const selected = getSelectedChannel(channels, selectedChannelId, selectedChannelYtId);
    if (selected) {
      return buildSelectedChannelContext(selected, t);
    }
    return buildGlobalContext(channels, settings, t);
  }

  window.buildHeaderContext = buildHeaderContext;
})();
