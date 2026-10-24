"GameInfo"
{
    game "Citadel asset tools"
    title "Citadel asset tools"
    GameData "citadel.fgd"
    LayeredOnMod core
    Engine2 { HasModAppSystems 0 }
    FileSystem
    {
        SteamAppId 1422450
        SearchPaths
        {
            Mod citadel
            Write citadel
            Game citadel
            Game core
            Mod core
            Game citadel_assets
            AddonRoot citadel_addons
            OfficialAddonRoot citadel_community_addons
        }
    }
    Hammer
    {
        fgd "citadel.fgd"
        GameFeatureSet CounterStrike
    }
    ModelDoc
    {
        models_gamedata "models_gamedata.fgd"
        features "animgraph;modelconfig"
    }
    // The lighting tool bakes on the GPU through Vulkan, and its scene
    // descriptor sets need descriptor indexing, which the render system
    // enables only when asked.
    RenderSystem
    {
        VulkanRequireSubgroupWaveOpSupport 1
        VulkanRequireDescriptorIndexing 1
    }
    // A map compile bakes lighting only when this block asks for it. The
    // channels are Deadlock's version 4 layout, which the CS2 lighting tool
    // writes and Deadlock still renders. Version 5 replaces the r, g and b
    // channels with one luminance channel that only Deadlock's own unreleased
    // lighting tool writes.
    ResourceCompiler
    {
        DefaultMapBuilders
        {
            bakedlighting 1
        }
        BakedLighting
        {
            Version 4
            ImportanceVolumeTransitionRegion 512
            LightmapChannels
            {
                direct_light_shadows 1
                debug_chart_color 1
                directional_irradiance_sh2_dc 1
                directional_irradiance_sh2_r { CompressedFormat DXT1 }
                directional_irradiance_sh2_g { CompressedFormat DXT1 }
                directional_irradiance_sh2_b { CompressedFormat DXT1 }
            }
            LightmapGutterSize 2
            UseStaticLightProbes 0
            LPVAtlas 1
        }
    }
}
