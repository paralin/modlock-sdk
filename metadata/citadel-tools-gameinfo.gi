// The toolkit's changes to the game's own gameinfo.gi. The installer applies
// them to the installed game's current file: each section here merges into the
// game's section key by key, and each value inside a section replaces the
// game's whole, so the search path list below replaces the game's list.
"GameInfo"
{
    game "Citadel asset tools"
    title "Citadel asset tools"
    LayeredOnMod core
    // Mod app systems load the game's server and client code, which only the
    // stationary light shadow atlas needs. The game's client would log on to
    // Steam under the player's account, and Deadlock ships no modtools.dll to
    // host the code anyway, so maps bake static lights.
    Engine2 { HasModAppSystems 0 }
    FileSystem
    {
        SteamAppId 1422450
        // core_deadlock holds Deadlock's core package ahead of the editors'
        // own core, so maps use the game's materials and shaders.
        SearchPaths
        {
            Mod citadel
            Write citadel
            Game citadel
            Game core_deadlock
            Game core
            Mod core
            Game citadel_assets
            AddonRoot citadel_addons
            OfficialAddonRoot citadel_community_addons
        }
        // The game keeps key bindings and settings in the player's Steam
        // profile folder. The editors write theirs under game/citadel/cfg
        // instead, so an editor session never changes the player's.
        UserSettingsPathID MOD
    }
    // The lighting tool bakes on the GPU through Vulkan, and its scene
    // descriptor sets need descriptor indexing, which the render system
    // enables only when asked. The game asks today; the bake needs it always.
    RenderSystem
    {
        VulkanRequireSubgroupWaveOpSupport 1
        VulkanRequireDescriptorIndexing 1
    }
    // With the game's Steam Audio runtime on, Hammer crashes drawing its first
    // frame. Steam Audio baking in the map compiler does not need it.
    SoundSystem { SteamAudioEnabled 0 }
    ResourceCompiler
    {
        // The game's post-build steps need its code: the PvE navigation cache
        // step crashes without it.
        GameSpecificPostMapBuildSteps { }
    }
}
