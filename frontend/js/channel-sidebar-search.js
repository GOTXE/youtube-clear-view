// Sidebar-specific channel filtering helpers.

(function () {
  function normalizeSidebarQuery(query) {
    return String(query || '').trim().toLowerCase();
  }

  function filterChannelsForSidebar(channels, query) {
    const normalizedQuery = normalizeSidebarQuery(query);
    const safeChannels = Array.isArray(channels) ? channels.slice() : [];

    if (!normalizedQuery) {
      return safeChannels;
    }

    return safeChannels.filter(channel => {
      const title = String(channel && channel.title ? channel.title : '').toLowerCase();
      const ytChannelId = String(channel && channel.yt_channel_id ? channel.yt_channel_id : '').toLowerCase();
      return title.includes(normalizedQuery) || ytChannelId.includes(normalizedQuery);
    });
  }

  window.normalizeSidebarQuery = normalizeSidebarQuery;
  window.filterChannelsForSidebar = filterChannelsForSidebar;
})();
