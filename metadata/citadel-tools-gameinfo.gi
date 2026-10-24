"GameInfo"
{
    game "Citadel asset tools"
    title "Citadel asset tools"
    GameData "citadel.fgd"
    LayeredOnMod core
    // Mod app systems load the game's server and client code, which only the
    // stationary light shadow atlas needs. Deadlock ships no modtools.dll to
    // host them, so maps bake static lights.
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
    }
    Hammer
    {
        fgd "citadel.fgd"
        GameFeatureSet Citadel
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
    // Deadlock's own map build settings. The game's post-build steps are left
    // out: its PvE navigation cache step crashes without the game's code.
    ResourceCompiler
    {
        ForceVulkanForMapBuild 1
        DefaultMapBuilders
        {
            bakedlighting 1
            envmap 0
            nav 1
            sareverb 0
            sapaths 0
            sacustomdata 1
        }
        MeshCompiler
        {
            OptimizeForMeshlets 1
            TrianglesPerMeshlet 64
            UseMikkTSpace 1
            EncodeVertexBuffer 1
            EncodeVertexBufferVersion 1
            EncodeVertexBufferLevel 3
            EncodeIndexBuffer 1
            SplitDepthStream 1
        }
        WorldRendererBuilder
        {
            VisibilityGuidedMeshClustering 1
            MinimumTrianglesPerClusteredMesh 8192
            MinimumVerticesPerClusteredMesh 8192
            MinimumVolumePerClusteredMesh 8192
            MaxPrecomputedVisClusterMembership 96
            MaxCullingBoundsGroups 128
            UseAggregateInstances 1
            AggregateInstancingMeshlets 1
            BakePropsWithExtraVertexStreams 1
            MergeTranslucents 1
            BakePrecomputedShadows 1
            BakePrecomputedShadowsForDirectionalLights 0
            BakePrecomputedDepthPyramids 0
            PrecomputedShadowmapAtlas 1
            PrecomputedShadowmapAtlasBorder 1
            // Matches SceneSystem FogCachedShadowTileSizeTools.
            PrecomputedShadowmapResolutionDefault 128
        }
        // Version 5 stores one luminance direction channel in place of the
        // r, g and b channels of version 4. The editors' lighting tool writes
        // only the version 4 channels; the vrad3.exe wrapper beside it turns
        // them into the luminance channel.
        BakedLighting
        {
            Version 5
            ImportanceVolumeTransitionRegion 512
            LightmapChannels
            {
                direct_light_shadows 1
                debug_chart_color 1
                directional_irradiance_sh2_dc 1
                directional_irradiance_sh2_lum { CompressedFormat DXT1 }
            }
            LightmapGutterSize 2
            UseStaticLightProbes 0
            LPVAtlas 1
        }
        SteamAudio
        {
            ReverbDefaults
            {
                GridGenerationType 0
                FilterUsingVolumes 1
                FilterUsingNavMesh 0
                GridSpacing 3.0
                HeightAboveFloor 1.5
                RebakeOption 0
                NumRays 32768
                NumBounces 64
                IRDuration 1.0
                AmbisonicsOrder 1
                ClusteringEnabled 0
                ClusteringCubemapResolution 16.0
                ClusteringDepthThreshold 10.0
            }
            PathingDefaults
            {
                GridGenerationType 0
                FilterUsingVolumes 1
                FilterUsingNavMesh 0
                GridSpacing 3.0
                HeightAboveFloor 1.5
                RebakeOption 0
                NumVisSamples 1
                ProbeVisRadius 0
                ProbeVisThreshold 0.1
                ProbeVisPathRange 1000.0
            }
            CustomDataDefaults
            {
                GridGenerationType 0
                FilterUsingVolumes 1
                FilterUsingNavMesh 1
                GridSpacing 6
                HeightAboveFloor 1.5
                RebakeOption 0
                BakeOcclusion 0
                BakeDimensions 1
                BakeMaterials 0
                OcclusionPathing 1
                OcclusionReflection 0
                OcclusionReflectionRays 16384
                OcclusionReflectionBounces 16
                DimensionsOutsideThreshold 0.02
            }
            ProbeGenerationVolumeDefaults
            {
                Spacing 3.0
                Height 1.5
                HeightSpacing 12
                UseForReverb 0
                UseForPathing 0
                UseForCustomData 1
                FilterUsingVolumes 1
                FilterUsingNavMesh 1
            }
        }
        VisBuilder
        {
            MaxVisClusters 4096
            PreMergeOpenSpaceDistanceThreshold 128.0
            PreMergeOpenSpaceMaxDimension 2048.0
            PreMergeOpenSpaceMaxRatio 8.0
            PreMergeSmallRegionsSizeThreshold 20.0
        }
        TextureCompiler
        {
            AllowNP2Textures 1
            AllowPanoramaMipGeneration 1
        }
    }
    // Deadlock's renderer settings, so the editors draw maps as the game does.
    SceneSystem
    {
        GpuLightBinner 1
        FogCachedShadowAtlasWidthTools 2048
        FogCachedShadowAtlasHeightTools 2048
        FogCachedShadowTileSizeTools 128
        GpuLightBinnerSunLightFastPath 1
        CSMCascadeResolution 2048
        SunLightManagerCount 0
        SunLightManagerCountTools 0
        DefaultShadowTextureWidth 6144
        DefaultShadowTextureHeight 6144
        DynamicShadowResolution 1
        TransformTextureRowCount 1024
        TransformTextureRowCountToolsMode 6144
        SunLightMaxCascadeSize 4
        SunLightShadowRenderMode Depth
        NonTexturedGradientFog 1
        CubemapFog 1
        VolumetricFog 1
        FrameBufferCopyFormat R11G11B10F
        Tonemapping 0
        WellKnownLightCookies
        {
            blank "materials/effects/lightcookies/blank.vtex"
            flashlight "materials/effects/lightcookies/flashlight.vtex"
        }
        ComputeShaderSkinning 1
    }
    WorldRenderer
    {
        EnvironmentMaps 1
        EnvironmentMapFaceSize 256
        EnvironmentMapRenderSize 1024
        EnvironmentMapFormat BC6H
        EnvironmentMapPreviewFormat BC6H
        EnvironmentMapColorSpace linear
        EnvironmentMapMipProcessor GGXCubeMapBlur
        EnvironmentMapUseCubeArray 1
        EnvironmentMapCacheSizeTools 300
        BindlessSceneObjectDesc CitadelBindlessDesc
        GrassCastsShadows 1
    }
}
