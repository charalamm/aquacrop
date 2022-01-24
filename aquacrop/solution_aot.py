__all__ = [
    "growing_degree_day",
    "root_zone_water",
    "check_groundwater_table",
    "root_development",
    "pre_irrigation",
    "drainage",
    "rainfall_partition",
    "irrigation",
    "infiltration",
    "capillary_rise",
    "germination",
    "growth_stage",
    "water_stress",
    "cc_development",
    "cc_required_time",
    "adjust_CCx",
    "update_CCx_CDC",
    "canopy_cover",
    "evap_layer_water_content",
    "soil_evaporation",
    "aeration_stress",
    "transpiration",
    "groundwater_inflow",
    "HIref_current_day",
    "biomass_accumulation",
    "temperature_stress",
    "HIadj_pre_anthesis",
    "HIadj_pollination",
    "HIadj_post_anthesis",
    "harvest_index",
]

# Cell
from .classes import *
import numpy as np
import pandas as pd

from numba.pycc import CC

cc = CC("solution_aot")

cc.verbose()


@cc.export("growing_degree_day", "f8(i4,f8,f8,f8,f8)")
def growing_degree_day(GDDmethod, Tupp, Tbase, Tmax, Tmin):
    """
    Function to calculate number of growing degree days on current day

    <a href="../pdfs/ac_ref_man_3.pdf#page=28" target="_blank">Reference manual: growing degree day calculations</a> (pg. 19-20)



    *Arguments:*

    `GDDmethod`: `int` : GDD calculation method

    `Tupp`: `float` : Upper temperature (degC) above which crop development no longer increases

    `Tbase`: `float` : Base temperature (degC) below which growth does not progress

    `Tmax`: `float` : Maximum tempature on current day (celcius)

    `Tmin`: `float` : Minimum tempature on current day (celcius)


    *Returns:*


    `GDD`: `float` : Growing degree days for current day



    """

    ## Calculate GDDs ##
    if GDDmethod == 1:
        # Method 1
        Tmean = (Tmax + Tmin) / 2
        Tmean = min(Tmean, Tupp)
        Tmean = max(Tmean, Tbase)
        GDD = Tmean - Tbase
    elif GDDmethod == 2:
        # Method 2
        Tmax = min(Tmax, Tupp)
        Tmax = max(Tmax, Tbase)

        Tmin = min(Tmin, Tupp)
        Tmin = max(Tmin, Tbase)

        Tmean = (Tmax + Tmin) / 2
        GDD = Tmean - Tbase
    elif GDDmethod == 3:
        # Method 3
        Tmax = min(Tmax, Tupp)
        Tmax = max(Tmax, Tbase)

        Tmin = min(Tmin, Tupp)
        Tmean = (Tmax + Tmin) / 2
        Tmean = max(Tmean, Tbase)
        GDD = Tmean - Tbase

    return GDD


# aot doesn't support python dicts or jitclasses. what to do here instead? numpy arrays?
@cc.export("root_zone_water", "f8(i4,f8,f8,f8,f8)")
def root_zone_water(prof, InitCond_Zroot, InitCond_th, Soil_zTop, Crop_Zmin, Crop_Aer):
    """
    Function to calculate actual & total available water in the rootzone at current time step


    <a href="../pdfs/ac_ref_man_3.pdf#page=14" target="_blank">Reference Manual: root-zone water calculations</a> (pg. 5-8)


    *Arguments:*

    `prof`: `SoilProfileClass` : jit class Object containing soil paramaters

    `InitCond_Zroot`: `float` : Initial rooting depth

    `InitCond_th`: `np.array` : Initial water content

    `Soil_zTop`: `float` : Top soil depth

    `Crop_Zmin`: `float` : crop minimum rooting depth

    `Crop_Aer`: `int` : number of aeration stress days

    *Returns:*

     `WrAct`: `float` :  Actual rootzone water content

     `Dr`: `DrClass` :  Depletion objection containing rootzone & topsoil depletion

     `TAW`: `TAWClass` :  `TAWClass` containing rootzone & topsoil total avalable water

     `thRZ`: `thRZClass` :  thRZ object conaining rootzone water content paramaters



    """

    ## Calculate root zone water content & available water ##
    # Compartments covered by the root zone
    rootdepth = round(np.maximum(InitCond_Zroot, Crop_Zmin), 2)
    comp_sto = np.argwhere(prof.dzsum >= rootdepth).flatten()[0]

    # Initialise counters
    WrAct = 0
    WrS = 0
    WrFC = 0
    WrWP = 0
    WrDry = 0
    WrAer = 0
    for ii in range(comp_sto + 1):
        # Fraction of compartment covered by root zone
        if prof.dzsum[ii] > rootdepth:
            factor = 1 - ((prof.dzsum[ii] - rootdepth) / prof.dz[ii])
        else:
            factor = 1

        # Actual water storage in root zone (mm)
        WrAct = WrAct + round(factor * 1000 * InitCond_th[ii] * prof.dz[ii], 2)
        # Water storage in root zone at saturation (mm)
        WrS = WrS + round(factor * 1000 * prof.th_s[ii] * prof.dz[ii], 2)
        # Water storage in root zone at field capacity (mm)
        WrFC = WrFC + round(factor * 1000 * prof.th_fc[ii] * prof.dz[ii], 2)
        # Water storage in root zone at permanent wilting point (mm)
        WrWP = WrWP + round(factor * 1000 * prof.th_wp[ii] * prof.dz[ii], 2)
        # Water storage in root zone at air dry (mm)
        WrDry = WrDry + round(factor * 1000 * prof.th_dry[ii] * prof.dz[ii], 2)
        # Water storage in root zone at aeration stress threshold (mm)
        WrAer = WrAer + round(factor * 1000 * (prof.th_s[ii] - (Crop_Aer / 100)) * prof.dz[ii], 2)

    if WrAct < 0:
        WrAct = 0

    # define total available water, depletion, root zone water content
    TAW = TAWClass()
    Dr = DrClass()
    thRZ = thRZClass()

    # Calculate total available water (m3/m3)
    TAW.Rz = max(WrFC - WrWP, 0.0)
    # Calculate soil water depletion (mm)
    Dr.Rz = min(WrFC - WrAct, TAW.Rz)

    # Actual root zone water content (m3/m3)
    thRZ.Act = WrAct / (rootdepth * 1000)
    # Root zone water content at saturation (m3/m3)
    thRZ.S = WrS / (rootdepth * 1000)
    # Root zone water content at field capacity (m3/m3)
    thRZ.FC = WrFC / (rootdepth * 1000)
    # Root zone water content at permanent wilting point (m3/m3)
    thRZ.WP = WrWP / (rootdepth * 1000)
    # Root zone water content at air dry (m3/m3)
    thRZ.Dry = WrDry / (rootdepth * 1000)
    # Root zone water content at aeration stress threshold (m3/m3)
    thRZ.Aer = WrAer / (rootdepth * 1000)

    ## Calculate top soil water content & available water ##
    if rootdepth > Soil_zTop:
        # Determine compartments covered by the top soil
        ztopdepth = round(Soil_zTop, 2)
        comp_sto = np.sum(prof.dzsum <= ztopdepth)
        # Initialise counters
        WrAct_Zt = 0
        WrFC_Zt = 0
        WrWP_Zt = 0
        # Calculate water storage in top soil
        assert comp_sto > 0

        for ii in range(comp_sto):

            # Fraction of compartment covered by root zone
            if prof.dzsum[ii] > ztopdepth:
                factor = 1 - ((prof.dzsum[ii] - ztopdepth) / prof.dz[ii])
            else:
                factor = 1

            # Actual water storage in top soil (mm)
            WrAct_Zt = WrAct_Zt + (factor * 1000 * InitCond_th[ii] * prof.dz[ii])
            # Water storage in top soil at field capacity (mm)
            WrFC_Zt = WrFC_Zt + (factor * 1000 * prof.th_fc[ii] * prof.dz[ii])
            # Water storage in top soil at permanent wilting point (mm)
            WrWP_Zt = WrWP_Zt + (factor * 1000 * prof.th_wp[ii] * prof.dz[ii])

        # Ensure available water in top soil is not less than zero
        if WrAct_Zt < 0:
            WrAct_Zt = 0

        # Calculate total available water in top soil (m3/m3)
        TAW.Zt = max(WrFC_Zt - WrWP_Zt, 0)
        # Calculate depletion in top soil (mm)
        Dr.Zt = min(WrFC_Zt - WrAct_Zt, TAW.Zt)
    else:
        # Set top soil depletions & TAW to root zone values
        Dr.Zt = Dr.Rz
        TAW.Zt = TAW.Rz

    return WrAct, Dr, TAW, thRZ


# Cell
@njit()
def check_groundwater_table(
    ClockStruct_TimeStepCounter, prof, NewCond, ParamStruct_WaterTable, zGW
):
    """
    Function to check for presence of a groundwater table, &, if present,
    to adjust compartment water contents & field capacities where necessary

    <a href="../pdfs/ac_ref_man_3.pdf#page=61" target="_blank">Reference manual: water table adjustment equations</a> (pg. 52-57)


    *Arguments:*

    `ClockStruct`: `ClockStructClass` : ClockStruct object containing clock paramaters

    `Soil`: `SoilClass` : Soil object containing soil paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `ParamStruct`: `ParamStructClass` :  model paramaters


    *Returns:*

    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `Soil`: `SoilClass` : Soil object containing updated soil paramaters




    """

    ## Perform calculations (if variable water table is present) ##
    if ParamStruct_WaterTable == 1:

        # Update groundwater conditions for current day
        NewCond.zGW = zGW

        # Find compartment mid-points
        zMid = prof.zMid

        # Check if water table is within modelled soil profile
        if NewCond.zGW >= 0:
            if len(zMid[zMid >= NewCond.zGW]) == 0:
                NewCond.WTinSoil = False
            else:
                NewCond.WTinSoil = True

        # If water table is in soil profile, adjust water contents
        if NewCond.WTinSoil == True:
            idx = np.argwhere(zMid >= NewCond.zGW).flatten()[0]
            for ii in range(idx, len(prof.Comp)):
                NewCond.th[ii] = prof.th_s[ii]

        # Adjust compartment field capacity
        compi = len(prof.Comp) - 1
        thfcAdj = np.zeros(compi + 1)
        # Find thFCadj for all compartments
        while compi >= 0:
            if prof.th_fc[compi] <= 0.1:
                Xmax = 1
            else:
                if prof.th_fc[compi] >= 0.3:
                    Xmax = 2
                else:
                    pF = 2 + 0.3 * (prof.th_fc[compi] - 0.1) / 0.2
                    Xmax = (np.exp(pF * np.log(10))) / 100

            if (NewCond.zGW < 0) or ((NewCond.zGW - zMid[compi]) >= Xmax):
                for ii in range(compi):

                    thfcAdj[ii] = prof.th_fc[ii]

                compi = -1
            else:
                if prof.th_fc[compi] >= prof.th_s[compi]:
                    thfcAdj[compi] = prof.th_fc[compi]
                else:
                    if zMid[compi] >= NewCond.zGW:
                        thfcAdj[compi] = prof.th_s[compi]
                    else:
                        dV = prof.th_s[compi] - prof.th_fc[compi]
                        dFC = (dV / (Xmax * Xmax)) * ((zMid[compi] - (NewCond.zGW - Xmax)) ** 2)
                        thfcAdj[compi] = prof.th_fc[compi] + dFC

                compi = compi - 1

        # Store adjusted field capacity values
        NewCond.th_fc_Adj = thfcAdj
        prof.th_fc_Adj = thfcAdj

    return NewCond, prof


# Cell
@njit()
def root_development(Crop, prof, InitCond, GDD, GrowingSeason, ParamStruct_WaterTable):
    """
    Function to calculate root zone expansion

    <a href="../pdfs/ac_ref_man_3.pdf#page=46" target="_blank">Reference Manual: root developement equations</a> (pg. 37-41)


    *Arguments:*

    `Crop`: `CropStruct` : jit class object containing Crop paramaters

    `prof`: `SoilProfileClass` : jit class object containing soil paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `GDD`: `float` : Growing degree days on current day

    `GrowingSeason`: `bool` : is growing season (True or Flase)

    `ParamStruct_WaterTable`: `int` : water table present (True=1 or Flase=0)


    *Returns:*

    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters


    """
    # Store initial conditions for updating
    NewCond = InitCond

    # save initial zroot
    Zroot_init = float(InitCond.Zroot) * 1.0
    Soil_nLayer = np.unique(prof.Layer).shape[0]

    # Calculate root expansion (if in growing season)
    if GrowingSeason == True:
        # If today is first day of season, root depth is equal to minimum depth
        if NewCond.DAP == 1:
            NewCond.Zroot = float(Crop.Zmin) * 1.0
            Zroot_init = float(Crop.Zmin) * 1.0

        # Adjust time for any delayed development
        if Crop.CalendarType == 1:
            tAdj = NewCond.DAP - NewCond.DelayedCDs
        elif Crop.CalendarType == 2:
            tAdj = NewCond.GDDcum - NewCond.DelayedGDDs

        # Calculate root expansion #
        Zini = Crop.Zmin * (Crop.PctZmin / 100)
        t0 = round((Crop.Emergence / 2))
        tmax = Crop.MaxRooting
        if Crop.CalendarType == 1:
            tOld = tAdj - 1
        elif Crop.CalendarType == 2:
            tOld = tAdj - GDD

        # Potential root depth on previous day
        if tOld >= tmax:
            ZrOld = Crop.Zmax
        elif tOld <= t0:
            ZrOld = Zini
        else:
            X = (tOld - t0) / (tmax - t0)
            ZrOld = Zini + (Crop.Zmax - Zini) * np.power(X, 1 / Crop.fshape_r)

        if ZrOld < Crop.Zmin:
            ZrOld = Crop.Zmin

        # Potential root depth on current day
        if tAdj >= tmax:
            Zr = Crop.Zmax
        elif tAdj <= t0:
            Zr = Zini
        else:
            X = (tAdj - t0) / (tmax - t0)
            Zr = Zini + (Crop.Zmax - Zini) * np.power(X, 1 / Crop.fshape_r)

        if Zr < Crop.Zmin:
            Zr = Crop.Zmin

        # Store Zr as potential value
        ZrPot = Zr

        # Determine rate of change
        dZr = Zr - ZrOld

        # Adjust expansion rate for presence of restrictive soil horizons
        if Zr > Crop.Zmin:
            layeri = 1
            l_idx = np.argwhere(prof.Layer == layeri).flatten()
            Zsoil = prof.dz[l_idx].sum()
            while (round(Zsoil, 2) <= Crop.Zmin) & (layeri < Soil_nLayer):
                layeri = layeri + 1
                l_idx = np.argwhere(prof.Layer == layeri).flatten()
                Zsoil = Zsoil + prof.dz[l_idx].sum()

            soil_layer_dz = prof.dz[l_idx].sum()
            layer_comp = l_idx[0]
            # soil_layer = prof.Layer[layeri]
            ZrAdj = Crop.Zmin
            ZrRemain = Zr - Crop.Zmin
            deltaZ = Zsoil - Crop.Zmin
            EndProf = False
            while EndProf == False:
                ZrTest = ZrAdj + (ZrRemain * (prof.Penetrability[layer_comp] / 100))
                if (
                    (layeri == Soil_nLayer)
                    or (prof.Penetrability[layer_comp] == 0)
                    or (ZrTest <= Zsoil)
                ):
                    ZrOUT = ZrTest
                    EndProf = True
                else:
                    ZrAdj = Zsoil
                    ZrRemain = ZrRemain - (deltaZ / (prof.Penetrability[layer_comp] / 100))
                    layeri = layeri + 1
                    l_idx = np.argwhere(prof.Layer == layeri).flatten()
                    layer_comp = l_idx[0]
                    soil_layer_dz = prof.dz[l_idx].sum()
                    Zsoil = Zsoil + soil_layer_dz
                    deltaZ = soil_layer_dz

            # Correct Zr & dZr for effects of restrictive horizons
            Zr = ZrOUT
            dZr = Zr - ZrOld

        # Adjust rate of expansion for any stomatal water stress
        if NewCond.TrRatio < 0.9999:
            if Crop.fshape_ex >= 0:
                dZr = dZr * NewCond.TrRatio
            else:
                fAdj = (np.exp(NewCond.TrRatio * Crop.fshape_ex) - 1) / (np.exp(Crop.fshape_ex) - 1)
                dZr = dZr * fAdj

        # print(NewCond.DAP,NewCond.th)

        # Adjust rate of root expansion for dry soil at expansion front
        if dZr > 0.001:
            # Define water stress threshold for inhibition of root expansion
            pZexp = Crop.p_up[1] + ((1 - Crop.p_up[1]) / 2)
            # Define potential new root depth
            ZiTmp = float(Zroot_init + dZr)
            # Find compartment that root zone will expand in to
            # compi_index = prof.dzsum[prof.dzsum>=ZiTmp].index[0] # have changed to index
            idx = np.argwhere(prof.dzsum >= ZiTmp).flatten()[0]
            prof = prof
            # Get TAW in compartment
            layeri = prof.Layer[idx]
            TAWprof = prof.th_fc[idx] - prof.th_wp[idx]
            # Define stress threshold
            thThr = prof.th_fc[idx] - (pZexp * TAWprof)
            # Check for stress conditions
            if NewCond.th[idx] < thThr:
                # Root expansion limited by water content at expansion front
                if NewCond.th[idx] <= prof.th_wp[idx]:

                    # Expansion fully inhibited
                    dZr = 0
                else:
                    # Expansion partially inhibited
                    Wrel = (prof.th_fc[idx] - NewCond.th[idx]) / TAWprof
                    Drel = 1 - ((1 - Wrel) / (1 - pZexp))
                    Ks = 1 - (
                        (np.exp(Drel * Crop.fshape_w[1]) - 1) / (np.exp(Crop.fshape_w[1]) - 1)
                    )
                    dZr = dZr * Ks

        # Adjust for early senescence
        if (NewCond.CC <= 0) & (NewCond.CC_NS > 0.5):
            dZr = 0

        # Adjust root expansion for failure to germinate (roots cannot expand
        # if crop has not germinated)
        if NewCond.Germination == False:
            dZr = 0

        # Get new rooting depth
        NewCond.Zroot = float(Zroot_init + dZr)

        # Adjust root density if deepening is restricted due to dry subsoil
        # &/or restrictive layers
        if NewCond.Zroot < ZrPot:
            NewCond.rCor = (
                2 * (ZrPot / NewCond.Zroot) * ((Crop.SxTop + Crop.SxBot) / 2) - Crop.SxTop
            ) / Crop.SxBot

            if NewCond.Tpot > 0:
                NewCond.rCor = NewCond.rCor * NewCond.TrRatio
                if NewCond.rCor < 1:
                    NewCond.rCor = 1

        else:
            NewCond.rCor = 1

        # Limit rooting depth if groundwater table is present (roots cannot
        # develop below the water table)
        if (ParamStruct_WaterTable == 1) & (NewCond.zGW > 0):
            if NewCond.Zroot > NewCond.zGW:
                NewCond.Zroot = float(NewCond.zGW)
                if NewCond.Zroot < Crop.Zmin:
                    NewCond.Zroot = float(Crop.Zmin)

    else:
        # No root system outside of the growing season
        NewCond.Zroot = 0

    return NewCond


# Cell
@njit()
def pre_irrigation(prof, Crop, InitCond, GrowingSeason, IrrMngt):
    """
    Function to calculate pre-irrigation when in net irrigation mode

    <a href="../pdfs/ac_ref_man_1.pdf#page=40" target="_blank">Reference Manual: Net irrigation description</a> (pg. 31)


    *Arguments:*

    `prof`: `SoilProfileClass` : Soil object containing soil paramaters

    `Crop`: `CropStruct` : Crop object containing Crop paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `GrowingSeason`: `bool` : is growing season (True or Flase)

    `IrrMngt`: ``IrrMngtStruct`  object containing irrigation management paramaters



    *Returns:*

    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `PreIrr`: `float` : Pre-Irrigaiton applied on current day mm




    """
    # Store initial conditions for updating ##
    NewCond = InitCond

    ## Calculate pre-irrigation needs ##
    if GrowingSeason == True:
        if (IrrMngt.IrrMethod != 4) or (NewCond.DAP != 1):
            # No pre-irrigation as not in net irrigation mode or not on first day
            # of the growing season
            PreIrr = 0
        else:
            # Determine compartments covered by the root zone
            rootdepth = round(max(NewCond.Zroot, Crop.Zmin), 2)

            compRz = np.argwhere(prof.dzsum >= rootdepth).flatten()[0]

            PreIrr = 0
            for ii in range(int(compRz)):

                # Determine critical water content threshold
                thCrit = prof.th_wp[ii] + (
                    (IrrMngt.NetIrrSMT / 100) * (prof.th_fc[ii] - prof.th_wp[ii])
                )

                # Check if pre-irrigation is required
                if NewCond.th[ii] < thCrit:
                    PreIrr = PreIrr + ((thCrit - NewCond.th[ii]) * 1000 * prof.dz[ii])
                    NewCond.th[ii] = thCrit

    else:
        PreIrr = 0

    return NewCond, PreIrr


# Cell
@njit()
def drainage(prof, th_init, th_fc_Adj_init):
    """
    Function to redistribute stored soil water



    <a href="../pdfs/ac_ref_man_3.pdf#page=51" target="_blank">Reference Manual: drainage calculations</a> (pg. 42-65)


    *Arguments:*



    `prof`: `SoilProfileClass` : jit class object object containing soil paramaters

    `th_init`: `np.array` : initial water content

    `th_fc_Adj_init`: `np.array` : adjusted water content at field capacity


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `DeepPerc`:: `float` : Total Deep Percolation

    `FluxOut`:: `array-like` : Flux of water out of each compartment





    """

    # Store initial conditions in new structure for updating %%
    #     NewCond = InitCond

    #     th_init = InitCond.th
    #     th_fc_Adj_init = InitCond.th_fc_Adj

    #  Preallocate arrays %%
    thnew = np.zeros(th_init.shape[0])
    FluxOut = np.zeros(th_init.shape[0])

    # Initialise counters & states %%
    drainsum = 0

    # Calculate drainage & updated water contents %%
    for ii in range(th_init.shape[0]):
        # Specify layer for compartment
        cth_fc = prof.th_fc[ii]
        cth_s = prof.th_s[ii]
        ctau = prof.tau[ii]
        cdz = prof.dz[ii]
        cdzsum = prof.dzsum[ii]
        cKsat = prof.Ksat[ii]

        # Calculate drainage ability of compartment ii
        if th_init[ii] <= th_fc_Adj_init[ii]:
            dthdt = 0

        elif th_init[ii] >= cth_s:
            dthdt = ctau * (cth_s - cth_fc)

            if (th_init[ii] - dthdt) < th_fc_Adj_init[ii]:
                dthdt = th_init[ii] - th_fc_Adj_init[ii]

        else:
            dthdt = (
                ctau
                * (cth_s - cth_fc)
                * ((np.exp(th_init[ii] - cth_fc) - 1) / (np.exp(cth_s - cth_fc) - 1))
            )

            if (th_init[ii] - dthdt) < th_fc_Adj_init[ii]:
                dthdt = th_init[ii] - th_fc_Adj_init[ii]

        # Drainage from compartment ii (mm)
        draincomp = dthdt * cdz * 1000

        # Check drainage ability of compartment ii against cumulative drainage
        # from compartments above
        excess = 0
        prethick = cdzsum - cdz
        drainmax = dthdt * 1000 * prethick
        if drainsum <= drainmax:
            drainability = True
        else:
            drainability = False

        # Drain compartment ii
        if drainability == True:
            # No storage needed. Update water content in compartment ii
            thnew[ii] = th_init[ii] - dthdt

            # Update cumulative drainage (mm)
            drainsum = drainsum + draincomp

            # Restrict cumulative drainage to saturated hydraulic
            # conductivity & adjust excess drainage flow
            if drainsum > cKsat:
                excess = excess + drainsum - cKsat
                drainsum = cKsat

        elif drainability == False:
            # Storage is needed
            dthdt = drainsum / (1000 * prethick)

            # Calculate value of theta (thX) needed to provide a
            # drainage ability equal to cumulative drainage
            if dthdt <= 0:
                thX = th_fc_Adj_init[ii]
            elif ctau > 0:
                A = 1 + ((dthdt * (np.exp(cth_s - cth_fc) - 1)) / (ctau * (cth_s - cth_fc)))
                thX = cth_fc + np.log(A)
                if thX < th_fc_Adj_init[ii]:
                    thX = th_fc_Adj_init[ii]

            else:
                thX = cth_s + 0.01

            # Check thX against hydraulic properties of current soil layer
            if thX <= cth_s:
                # Increase compartment ii water content with cumulative
                # drainage
                thnew[ii] = th_init[ii] + (drainsum / (1000 * cdz))
                # Check updated water content against thX
                if thnew[ii] > thX:
                    # Cumulative drainage is the drainage difference
                    # between theta_x & new theta plus drainage ability
                    # at theta_x.
                    drainsum = (thnew[ii] - thX) * 1000 * cdz
                    # Calculate drainage ability for thX
                    if thX <= th_fc_Adj_init[ii]:
                        dthdt = 0
                    elif thX >= cth_s:
                        dthdt = ctau * (cth_s - cth_fc)
                        if (thX - dthdt) < th_fc_Adj_init[ii]:
                            dthdt = thX - th_fc_Adj_init[ii]

                    else:
                        dthdt = (
                            ctau
                            * (cth_s - cth_fc)
                            * ((np.exp(thX - cth_fc) - 1) / (np.exp(cth_s - cth_fc) - 1))
                        )

                        if (thX - dthdt) < th_fc_Adj_init[ii]:
                            dthdt = thX - th_fc_Adj_init[ii]

                    # Update drainage total
                    drainsum = drainsum + (dthdt * 1000 * cdz)
                    # Restrict cumulative drainage to saturated hydraulic
                    # conductivity & adjust excess drainage flow
                    if drainsum > cKsat:
                        excess = excess + drainsum - cKsat
                        drainsum = cKsat

                    # Update water content
                    thnew[ii] = thX - dthdt

                elif thnew[ii] > th_fc_Adj_init[ii]:
                    # Calculate drainage ability for updated water content
                    if thnew[ii] <= th_fc_Adj_init[ii]:
                        dthdt = 0
                    elif thnew[ii] >= cth_s:
                        dthdt = ctau * (cth_s - cth_fc)
                        if (thnew[ii] - dthdt) < th_fc_Adj_init[ii]:
                            dthdt = thnew[ii] - th_fc_Adj_init[ii]

                    else:
                        dthdt = (
                            ctau
                            * (cth_s - cth_fc)
                            * ((np.exp(thnew[ii] - cth_fc) - 1) / (np.exp(cth_s - cth_fc) - 1))
                        )
                        if (thnew[ii] - dthdt) < th_fc_Adj_init[ii]:
                            dthdt = thnew[ii] - th_fc_Adj_init[ii]

                    # Update water content in compartment ii
                    thnew[ii] = thnew[ii] - dthdt
                    # Update cumulative drainage
                    drainsum = dthdt * 1000 * cdz
                    # Restrict cumulative drainage to saturated hydraulic
                    # conductivity & adjust excess drainage flow
                    if drainsum > cKsat:
                        excess = excess + drainsum - cKsat
                        drainsum = cKsat

                else:
                    # Drainage & cumulative drainage are zero as water
                    # content has not risen above field capacity in
                    # compartment ii.
                    drainsum = 0

            elif thX > cth_s:
                # Increase water content in compartment ii with cumulative
                # drainage from above
                thnew[ii] = th_init[ii] + (drainsum / (1000 * cdz))
                # Check new water content against hydraulic properties of soil
                # layer
                if thnew[ii] <= cth_s:
                    if thnew[ii] > th_fc_Adj_init[ii]:
                        # Calculate new drainage ability
                        if thnew[ii] <= th_fc_Adj_init[ii]:
                            dthdt = 0
                        elif thnew[ii] >= cth_s:
                            dthdt = ctau * (cth_s - cth_fc)
                            if (thnew[ii] - dthdt) < th_fc_Adj_init[ii]:
                                dthdt = thnew[ii] - th_fc_Adj_init[ii]

                        else:
                            dthdt = (
                                ctau
                                * (cth_s - cth_fc)
                                * ((np.exp(thnew[ii] - cth_fc) - 1) / (np.exp(cth_s - cth_fc) - 1))
                            )
                            if (thnew[ii] - dthdt) < th_fc_Adj_init[ii]:
                                dthdt = thnew[ii] - th_fc_Adj_init[ii]

                        # Update water content in compartment ii
                        thnew[ii] = thnew[ii] - dthdt
                        # Update cumulative drainage
                        drainsum = dthdt * 1000 * cdz
                        # Restrict cumulative drainage to saturated hydraulic
                        # conductivity & adjust excess drainage flow
                        if drainsum > cKsat:
                            excess = excess + drainsum - cKsat
                            drainsum = cKsat

                    else:
                        drainsum = 0

                elif thnew[ii] > cth_s:
                    # Calculate excess drainage above saturation
                    excess = (thnew[ii] - cth_s) * 1000 * cdz
                    # Calculate drainage ability for updated water content
                    if thnew[ii] <= th_fc_Adj_init[ii]:
                        dthdt = 0
                    elif thnew[ii] >= cth_s:
                        dthdt = ctau * (cth_s - cth_fc)
                        if (thnew[ii] - dthdt) < th_fc_Adj_init[ii]:
                            dthdt = thnew[ii] - th_fc_Adj_init[ii]

                    else:
                        dthdt = (
                            ctau
                            * (cth_s - cth_fc)
                            * ((np.exp(thnew[ii] - cth_fc) - 1) / (np.exp(cth_s - cth_fc) - 1))
                        )
                        if (thnew[ii] - dthdt) < th_fc_Adj_init[ii]:
                            dthdt = thnew[ii] - th_fc_Adj_init[ii]

                    # Update water content in compartment ii
                    thnew[ii] = cth_s - dthdt

                    # Update drainage from compartment ii
                    draincomp = dthdt * 1000 * cdz
                    # Update maximum drainage
                    drainmax = dthdt * 1000 * prethick

                    # Update excess drainage
                    if drainmax > excess:
                        drainmax = excess

                    excess = excess - drainmax
                    # Update drainsum & restrict to saturated hydraulic
                    # conductivity of soil layer
                    drainsum = draincomp + drainmax
                    if drainsum > cKsat:
                        excess = excess + drainsum - cKsat
                        drainsum = cKsat

        # Store output flux from compartment ii
        FluxOut[ii] = drainsum

        # Redistribute excess in compartment above
        if excess > 0:
            precomp = ii + 1
            while (excess > 0) & (precomp != 0):
                # Update compartment counter
                precomp = precomp - 1
                # Update layer counter
                # precompdf = Soil.Profile.Comp[precomp]

                # Update flux from compartment
                if precomp < ii:
                    FluxOut[precomp] = FluxOut[precomp] - excess

                # Increase water content to store excess
                thnew[precomp] = thnew[precomp] + (excess / (1000 * prof.dz[precomp]))

                # Limit water content to saturation & adjust excess counter
                if thnew[precomp] > prof.th_s[precomp]:
                    excess = (thnew[precomp] - prof.th_s[precomp]) * 1000 * prof.dz[precomp]
                    thnew[precomp] = prof.th_s[precomp]
                else:
                    excess = 0

    ## Update conditions & outputs ##
    # Total deep percolation (mm)
    DeepPerc = drainsum
    # Water contents
    # NewCond.th = thnew

    return thnew, DeepPerc, FluxOut


# Cell
@njit()
def rainfall_partition(P, InitCond, FieldMngt, Soil_CN, Soil_AdjCN, Soil_zCN, Soil_nComp, prof):
    """
    Function to partition rainfall into surface runoff & infiltration using the curve number approach


    <a href="../pdfs/ac_ref_man_3.pdf#page=57" target="_blank">Reference Manual: rainfall partition calculations</a> (pg. 48-51)



    *Arguments:*


    `P`: `float` : Percipitation on current day

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `FieldMngt`: `FieldMngtStruct` : field management params

    `Soil_CN`: `float` : curve number

    `Soil_AdjCN`: `float` : adjusted curve number

    `Soil_zCN`: `float` :

    `Soil_nComp`: `float` : number of compartments

    `prof`: `SoilProfileClass` : Soil object


    *Returns:*

    `Runoff`: `float` : Total Suface Runoff

    `Infl`: `float` : Total Infiltration

    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters






    """

    # can probs make this faster by doing a if P=0 loop

    ## Store initial conditions for updating ##
    NewCond = InitCond

    ## Calculate runoff ##
    if (FieldMngt.SRinhb == False) & ((FieldMngt.Bunds == False) or (FieldMngt.zBund < 0.001)):
        # Surface runoff is not inhibited & no soil bunds are on field
        # Reset submerged days
        NewCond.DaySubmerged = 0
        # Adjust curve number for field management practices
        CN = Soil_CN * (1 + (FieldMngt.CNadjPct / 100))
        if Soil_AdjCN == 1:  # Adjust CN for antecedent moisture
            # Calculate upper & lowe curve number bounds
            CNbot = round(
                1.4 * (np.exp(-14 * np.log(10)))
                + (0.507 * CN)
                - (0.00374 * CN ** 2)
                + (0.0000867 * CN ** 3)
            )
            CNtop = round(
                5.6 * (np.exp(-14 * np.log(10)))
                + (2.33 * CN)
                - (0.0209 * CN ** 2)
                + (0.000076 * CN ** 3)
            )
            # Check which compartment cover depth of top soil used to adjust
            # curve number
            comp_sto_array = prof.dzsum[prof.dzsum >= Soil_zCN]
            if comp_sto_array.shape[0] == 0:
                comp_sto = int(Soil_nComp)
            else:
                comp_sto = int(Soil_nComp - comp_sto_array.shape[0])

            # Calculate weighting factors by compartment
            xx = 0
            wrel = np.zeros(comp_sto)
            for ii in range(comp_sto):
                if prof.dzsum[ii] > Soil_zCN:
                    prof.dzsum[ii] = Soil_zCN

                wx = 1.016 * (1 - np.exp(-4.16 * (prof.dzsum[ii] / Soil_zCN)))
                wrel[ii] = wx - xx
                if wrel[ii] < 0:
                    wrel[ii] = 0
                elif wrel[ii] > 1:
                    wrel[ii] = 1

                xx = wx

            # Calculate relative wetness of top soil
            wet_top = 0
            prof = prof

            for ii in range(comp_sto):
                th = max(prof.th_wp[ii], InitCond.th[ii])
                wet_top = wet_top + (
                    wrel[ii] * ((th - prof.th_wp[ii]) / (prof.th_fc[ii] - prof.th_wp[ii]))
                )

            # Calculate adjusted curve number
            if wet_top > 1:
                wet_top = 1
            elif wet_top < 0:
                wet_top = 0

            CN = round(CNbot + (CNtop - CNbot) * wet_top)

        # Partition rainfall into runoff & infiltration (mm)
        S = (25400 / CN) - 254
        term = P - ((5 / 100) * S)
        if term <= 0:
            Runoff = 0
            Infl = P
        else:
            Runoff = (term ** 2) / (P + (1 - (5 / 100)) * S)
            Infl = P - Runoff

    else:
        # Bunds on field, therefore no surface runoff
        Runoff = 0
        Infl = P

    return Runoff, Infl, NewCond


# Cell
@njit()
def irrigation(InitCond, IrrMngt, Crop, prof, Soil_zTop, GrowingSeason, Rain, Runoff):
    """
    Function to get irrigation depth for current day



    <a href="../pdfs/ac_ref_man_1.pdf#page=40" target="_blank">Reference Manual: irrigation description</a> (pg. 31-32)


    *Arguments:*


    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `IrrMngt`: `IrrMngtStruct`: jit class object containing irrigation management paramaters

    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `Soil`: `SoilClass` : Soil object containing soil paramaters

    `GrowingSeason`: `bool` : is growing season (True or Flase)

    `Rain`: `float` : daily precipitation mm

    `Runoff`: `float` : surface runoff on current day


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `Irr`: `float` : Irrigaiton applied on current day mm

"""
    ## Store intial conditions for updating ##
    NewCond = InitCond

    ## Determine irrigation depth (mm/day) to be applied ##
    if GrowingSeason == True:
        # Calculate root zone water content & depletion
        WrAct, Dr_, TAW_, thRZ = root_zone_water(
            prof, float(NewCond.Zroot), NewCond.th, Soil_zTop, float(Crop.Zmin), Crop.Aer
        )
        # Use root zone depletions & TAW only for triggering irrigation
        Dr = Dr_.Rz
        TAW = TAW_.Rz

        # Determine adjustment for inflows & outflows on current day #
        if thRZ.Act > thRZ.FC:
            rootdepth = max(InitCond.Zroot, Crop.Zmin)
            AbvFc = (thRZ.Act - thRZ.FC) * 1000 * rootdepth
        else:
            AbvFc = 0

        WCadj = InitCond.Tpot + InitCond.Epot - Rain + Runoff - AbvFc

        NewCond.Depletion = Dr + WCadj
        NewCond.TAW = TAW

        # Update growth stage if it is first day of a growing season
        if NewCond.DAP == 1:
            NewCond.GrowthStage = 1

        if IrrMngt.IrrMethod == 0:
            Irr = 0

        elif IrrMngt.IrrMethod == 1:

            Dr = NewCond.Depletion / NewCond.TAW
            index = int(NewCond.GrowthStage) - 1

            if Dr > 1 - IrrMngt.SMT[index] / 100:
                # Irrigation occurs
                IrrReq = max(0, NewCond.Depletion)
                # Adjust irrigation requirements for application efficiency
                EffAdj = ((100 - IrrMngt.AppEff) + 100) / 100
                IrrReq = IrrReq * EffAdj
                # Limit irrigation to maximum depth
                Irr = min(IrrMngt.MaxIrr, IrrReq)
            else:
                Irr = 0

        elif IrrMngt.IrrMethod == 2:  # Irrigation - fixed interval

            Dr = NewCond.Depletion

            # Get number of days in growing season so far (subtract 1 so that
            # always irrigate first on day 1 of each growing season)
            nDays = NewCond.DAP - 1

            if nDays % IrrMngt.IrrInterval == 0:
                # Irrigation occurs
                IrrReq = max(0, Dr)
                # Adjust irrigation requirements for application efficiency
                EffAdj = ((100 - IrrMngt.AppEff) + 100) / 100
                IrrReq = IrrReq * EffAdj
                # Limit irrigation to maximum depth
                Irr = min(IrrMngt.MaxIrr, IrrReq)
            else:
                # No irrigation
                Irr = 0

        elif IrrMngt.IrrMethod == 3:  # Irrigation - pre-defined schedule
            # Get current date
            idx = NewCond.TimeStepCounter
            # Find irrigation value corresponding to current date
            Irr = IrrMngt.Schedule[idx]

            assert Irr >= 0

            Irr = min(IrrMngt.MaxIrr, Irr)

        elif IrrMngt.IrrMethod == 4:  # Irrigation - net irrigation
            # Net irrigation calculation performed after transpiration, so
            # irrigation is zero here

            Irr = 0

        elif IrrMngt.IrrMethod == 5:  # depth applied each day (usually specified outside of model)

            Irr = min(IrrMngt.MaxIrr, IrrMngt.depth)

        #         else:
        #             assert 1 ==2, f'somethings gone wrong in irrigation method:{IrrMngt.IrrMethod}'

        Irr = max(0, Irr)

    elif GrowingSeason == False:
        # No irrigation outside growing season
        Irr = 0
        NewCond.IrrCum = 0

    if NewCond.IrrCum + Irr > IrrMngt.MaxIrrSeason:
        Irr = max(0, IrrMngt.MaxIrrSeason - NewCond.IrrCum)

    # Update cumulative irrigation counter for growing season
    NewCond.IrrCum = NewCond.IrrCum + Irr

    return NewCond, Irr


# Cell
@njit()
def infiltration(
    prof, InitCond, Infl, Irr, IrrMngt_AppEff, FieldMngt, FluxOut, DeepPerc0, Runoff0, GrowingSeason
):
    """
    Function to infiltrate incoming water (rainfall & irrigation)

    <a href="../pdfs/ac_ref_man_3.pdf#page=51" target="_blank">Reference Manual: drainage calculations</a> (pg. 42-65)



    *Arguments:*



    `prof`: `SoilProfileClass` : Soil object containing soil paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Infl`: `float` : Infiltration so far

    `Irr`: `float` : Irrigation on current day

    `IrrMngt_AppEff`: `float`: irrigation application efficiency

    `FieldMngt`: `FieldMngtStruct` : field management params

    `FluxOut`: `np.array` : flux of water out of each compartment

    `DeepPerc0`: `float` : initial Deep Percolation

    `Runoff0`: `float` : initial Surface Runoff

    `GrowingSeason`:: `bool` : is growing season (True or Flase)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `DeepPerc`:: `float` : Total Deep Percolation

    `RunoffTot`: `float` : Total surface Runoff

    `Infl`: `float` : Infiltration on current day

    `FluxOut`: `np.array` : flux of water out of each compartment




    """
    ## Store initial conditions in new structure for updating ##
    NewCond = InitCond

    InitCond_SurfaceStorage = InitCond.SurfaceStorage
    InitCond_th_fc_Adj = InitCond.th_fc_Adj
    InitCond_th = InitCond.th

    thnew = NewCond.th.copy()

    Soil_nComp = thnew.shape[0]

    ## Update infiltration rate for irrigation ##
    # Note: irrigation amount adjusted for specified application efficiency
    if GrowingSeason == True:
        Infl = Infl + (Irr * (IrrMngt_AppEff / 100))

    assert Infl >= 0

    ## Determine surface storage (if bunds are present) ##
    if FieldMngt.Bunds:
        # Bunds on field
        if FieldMngt.zBund > 0.001:
            # Bund height too small to be considered
            InflTot = Infl + NewCond.SurfaceStorage
            if InflTot > 0:
                # Update surface storage & infiltration storage
                if InflTot > prof.Ksat[0]:
                    # Infiltration limited by saturated hydraulic conductivity
                    # of surface soil layer
                    ToStore = prof.Ksat[0]
                    # Additional water ponds on surface
                    NewCond.SurfaceStorage = InflTot - prof.Ksat[0]
                else:
                    # All water infiltrates
                    ToStore = InflTot
                    # Reset surface storage depth to zero
                    NewCond.SurfaceStorage = 0

                # Calculate additional runoff
                if NewCond.SurfaceStorage > (FieldMngt.zBund * 1000):
                    # Water overtops bunds & runs off
                    RunoffIni = NewCond.SurfaceStorage - (FieldMngt.zBund * 1000)
                    # Surface storage equal to bund height
                    NewCond.SurfaceStorage = FieldMngt.zBund * 1000
                else:
                    # No overtopping of bunds
                    RunoffIni = 0

            else:
                # No storage or runoff
                ToStore = 0
                RunoffIni = 0

    elif FieldMngt.Bunds == False:
        # No bunds on field
        if Infl > prof.Ksat[0]:
            # Infiltration limited by saturated hydraulic conductivity of top
            # soil layer
            ToStore = prof.Ksat[0]
            # Additional water runs off
            RunoffIni = Infl - prof.Ksat[0]
        else:
            # All water infiltrates
            ToStore = Infl
            RunoffIni = 0

        # Update surface storage
        NewCond.SurfaceStorage = 0
        # Add any water remaining behind bunds to surface runoff (needed for
        # days when bunds are removed to maintain water balance)
        RunoffIni = RunoffIni + InitCond_SurfaceStorage

    ## Initialise counters
    ii = -1
    Runoff = 0
    ## Infiltrate incoming water ##
    if ToStore > 0:
        while (ToStore > 0) & (ii < Soil_nComp - 1):
            # Update compartment counter
            ii = ii + 1
            # Get soil layer

            # Calculate saturated drainage ability
            dthdtS = prof.tau[ii] * (prof.th_s[ii] - prof.th_fc[ii])
            # Calculate drainage factor
            factor = prof.Ksat[ii] / (dthdtS * 1000 * prof.dz[ii])

            # Calculate drainage ability required
            dthdt0 = ToStore / (1000 * prof.dz[ii])

            # Check drainage ability
            if dthdt0 < dthdtS:
                # Calculate water content, thX, needed to meet drainage dthdt0
                if dthdt0 <= 0:
                    theta0 = InitCond_th_fc_Adj[ii]
                else:
                    A = 1 + (
                        (dthdt0 * (np.exp(prof.th_s[ii] - prof.th_fc[ii]) - 1))
                        / (prof.tau[ii] * (prof.th_s[ii] - prof.th_fc[ii]))
                    )

                    theta0 = prof.th_fc[ii] + np.log(A)

                # Limit thX to between saturation & field capacity
                if theta0 > prof.th_s[ii]:
                    theta0 = prof.th_s[ii]
                elif theta0 <= InitCond_th_fc_Adj[ii]:
                    theta0 = InitCond_th_fc_Adj[ii]
                    dthdt0 = 0

            else:
                # Limit water content & drainage to saturation
                theta0 = prof.th_s[ii]
                dthdt0 = dthdtS

            # Calculate maximum water flow through compartment ii
            drainmax = factor * dthdt0 * 1000 * prof.dz[ii]
            # Calculate total drainage from compartment ii
            drainage = drainmax + FluxOut[ii]
            # Limit drainage to saturated hydraulic conductivity
            if drainage > prof.Ksat[ii]:
                drainmax = prof.Ksat[ii] - FluxOut[ii]

            # Calculate difference between threshold & current water contents
            diff = theta0 - InitCond_th[ii]

            if diff > 0:
                # Increase water content of compartment ii
                thnew[ii] = thnew[ii] + (ToStore / (1000 * prof.dz[ii]))
                if thnew[ii] > theta0:
                    # Water remaining that can infiltrate to compartments below
                    ToStore = (thnew[ii] - theta0) * 1000 * prof.dz[ii]
                    thnew[ii] = theta0
                else:
                    # All infiltrating water has been stored
                    ToStore = 0

            # Update outflow from current compartment (drainage + infiltration
            # flows)
            FluxOut[ii] = FluxOut[ii] + ToStore

            # Calculate back-up of water into compartments above
            excess = ToStore - drainmax
            if excess < 0:
                excess = 0

            # Update water to store
            ToStore = ToStore - excess

            # Redistribute excess to compartments above
            if excess > 0:
                precomp = ii + 1
                while (excess > 0) & (precomp != 0):
                    # Keep storing in compartments above until soil surface is
                    # reached
                    # Update compartment counter
                    precomp = precomp - 1
                    # Update layer number

                    # Update outflow from compartment
                    FluxOut[precomp] = FluxOut[precomp] - excess
                    # Update water content
                    thnew[precomp] = thnew[precomp] + (excess / (prof.dz[precomp] * 1000))
                    # Limit water content to saturation
                    if thnew[precomp] > prof.th_s[precomp]:
                        # Update excess to store
                        excess = (thnew[precomp] - prof.th_s[precomp]) * 1000 * prof.dz[precomp]
                        # Set water content to saturation
                        thnew[precomp] = prof.th_s[precomp]
                    else:
                        # All excess stored
                        excess = 0

                if excess > 0:
                    # Any leftover water not stored becomes runoff
                    Runoff = Runoff + excess

        # Infiltration left to store after bottom compartment becomes deep
        # percolation (mm)
        DeepPerc = ToStore
    else:
        # No infiltration
        DeepPerc = 0
        Runoff = 0

    ## Update total runoff ##
    Runoff = Runoff + RunoffIni

    ## Update surface storage (if bunds are present) ##
    if Runoff > RunoffIni:
        if FieldMngt.Bunds:
            if FieldMngt.zBund > 0.001:
                # Increase surface storage
                NewCond.SurfaceStorage = NewCond.SurfaceStorage + (Runoff - RunoffIni)
                # Limit surface storage to bund height
                if NewCond.SurfaceStorage > (FieldMngt.zBund * 1000):
                    # Additonal water above top of bunds becomes runoff
                    Runoff = RunoffIni + (NewCond.SurfaceStorage - (FieldMngt.zBund * 1000))
                    # Set surface storage to bund height
                    NewCond.SurfaceStorage = FieldMngt.zBund * 1000
                else:
                    # No additional overtopping of bunds
                    Runoff = RunoffIni

    ## Store updated water contents ##
    NewCond.th = thnew

    ## Update deep percolation, surface runoff, & infiltration values ##
    DeepPerc = DeepPerc + DeepPerc0
    Infl = Infl - Runoff
    RunoffTot = Runoff + Runoff0

    return NewCond, DeepPerc, RunoffTot, Infl, FluxOut


# Cell
@njit()
def capillary_rise(prof, Soil_nLayer, Soil_fshape_cr, NewCond, FluxOut, ParamStruct_WaterTable):
    """
    Function to calculate capillary rise from a shallow groundwater table


    <a href="../pdfs/ac_ref_man_3.pdf#page=61" target="_blank">Reference Manual: capillary rise calculations</a> (pg. 52-61)


    *Arguments:*



    `Soil`: `SoilClass` : Soil object

    `NewCond`: `InitCondClass` : InitCond object containing model paramaters

    `FluxOut`: `np.array` : FLux of water out of each soil compartment

    `ParamStruct_WaterTable`: `int` : WaterTable present (1:yes, 0:no)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `CrTot`: `float` : Total Capillary rise





    """

    ## Get groundwater table elevation on current day ##
    zGW = NewCond.zGW

    ## Calculate capillary rise ##
    if ParamStruct_WaterTable == 0:  # No water table present
        # Capillary rise is zero
        CrTot = 0
    elif ParamStruct_WaterTable == 1:  # Water table present
        # Get maximum capillary rise for bottom compartment
        zBot = prof.dzsum[-1]
        zBotMid = prof.zMid[-1]
        prof = prof
        if (prof.Ksat[-1] > 0) & (zGW > 0) & ((zGW - zBotMid) < 4):
            if zBotMid >= zGW:
                MaxCR = 99
            else:
                MaxCR = np.exp((np.log(zGW - zBotMid) - prof.bCR[-1]) / prof.aCR[-1])
                if MaxCR > 99:
                    MaxCR = 99

        else:
            MaxCR = 0

        ######################### this needs fixing, will currently break####################

        #         # Find top of next soil layer that is not within modelled soil profile
        #         zTopLayer = 0
        #         for layeri in np.sort(np.unique(prof.Layer)):
        #             # Calculate layer thickness
        #             l_idx = np.argwhere(prof.Layer==layeri).flatten()

        #             LayThk = prof.dz[l_idx].sum()
        #             zTopLayer = zTopLayer+LayThk

        #         # Check for restrictions on upward flow caused by properties of
        #         # compartments that are not modelled in the soil water balance
        #         layeri = prof.Layer[-1]

        #         assert layeri == Soil_nLayer

        #         while (zTopLayer < zGW) & (layeri < Soil_nLayer):
        #             # this needs fixing, will currently break

        #             layeri = layeri+1
        #             compdf = prof.Layer[layeri]
        #             if (compdf.Ksat > 0) & (zGW > 0) & ((zGW-zTopLayer) < 4):
        #                 if zTopLayer >= zGW:
        #                     LimCR = 99
        #                 else:
        #                     LimCR = np.exp((np.log(zGW-zTopLayer)-compdf.bCR)/compdf.aCR)
        #                     if LimCR > 99:
        #                         LimCR = 99

        #             else:
        #                 LimCR = 0

        #             if MaxCR > LimCR:
        #                 MaxCR = LimCR

        #             zTopLayer = zTopLayer+compdf.dz

        #####################################################################################

        # Calculate capillary rise
        compi = len(prof.Comp) - 1  # Start at bottom of root zone
        WCr = 0  # Capillary rise counter
        while (round(MaxCR * 1000) > 0) & (compi > -1) & (round(FluxOut[compi] * 1000) == 0):
            # Proceed upwards until maximum capillary rise occurs, soil surface
            # is reached, or encounter a compartment where downward
            # drainage/infiltration has already occurred on current day
            # Find layer of current compartment
            # Calculate driving force
            if (NewCond.th[compi] >= prof.th_wp[compi]) & (Soil_fshape_cr > 0):
                Df = 1 - (
                    (
                        (NewCond.th[compi] - prof.th_wp[compi])
                        / (NewCond.th_fc_Adj[compi] - prof.th_wp[compi])
                    )
                    ** Soil_fshape_cr
                )
                if Df > 1:
                    Df = 1
                elif Df < 0:
                    Df = 0

            else:
                Df = 1

            # Calculate relative hydraulic conductivity
            thThr = (prof.th_wp[compi] + prof.th_fc[compi]) / 2
            if NewCond.th[compi] < thThr:
                if (NewCond.th[compi] <= prof.th_wp[compi]) or (thThr <= prof.th_wp[compi]):
                    Krel = 0
                else:
                    Krel = (NewCond.th[compi] - prof.th_wp[compi]) / (thThr - prof.th_wp[compi])

            else:
                Krel = 1

            # Check if room is available to store water from capillary rise
            dth = NewCond.th_fc_Adj[compi] - NewCond.th[compi]

            # Store water if room is available
            if (dth > 0) & ((zBot - prof.dz[compi] / 2) < zGW):
                dthMax = Krel * Df * MaxCR / (1000 * prof.dz[compi])
                if dth >= dthMax:
                    NewCond.th[compi] = NewCond.th[compi] + dthMax
                    CRcomp = dthMax * 1000 * prof.dz[compi]
                    MaxCR = 0
                else:
                    NewCond.th[compi] = NewCond.th_fc_Adj[compi]
                    CRcomp = dth * 1000 * prof.dz[compi]
                    MaxCR = (Krel * MaxCR) - CRcomp

                WCr = WCr + CRcomp

            # Update bottom elevation of compartment
            zBot = zBot - prof.dz[compi]
            # Update compartment & layer counters
            compi = compi - 1
            # Update restriction on maximum capillary rise
            if compi > -1:

                zBotMid = zBot - (prof.dz[compi] / 2)
                if (prof.Ksat[compi] > 0) & (zGW > 0) & ((zGW - zBotMid) < 4):
                    if zBotMid >= zGW:
                        LimCR = 99
                    else:
                        LimCR = np.exp((np.log(zGW - zBotMid) - prof.bCR[compi]) / prof.aCR[compi])
                        if LimCR > 99:
                            LimCR = 99

                else:
                    LimCR = 0

                if MaxCR > LimCR:
                    MaxCR = LimCR

        # Store total depth of capillary rise
        CrTot = WCr

    return NewCond, CrTot


# Cell
@njit()
def germination(InitCond, Soil_zGerm, prof, Crop_GermThr, Crop_PlantMethod, GDD, GrowingSeason):
    """
    Function to check if crop has germinated


    <a href="../pdfs/ac_ref_man_3.pdf#page=32" target="_blank">Reference Manual: germination condition</a> (pg. 23)


    *Arguments:*


    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Soil_zGerm`: `float` : Soil depth affecting germination

    `prof`: `SoilProfileClass` : Soil object containing soil paramaters

    `Crop_GermThr`: `float` : Crop germination threshold

    `Crop_PlantMethod`: `bool` : sown as seedling True or False

    `GDD`: `float` : Number of Growing Degree Days on current day

    `GrowingSeason`:: `bool` : is growing season (True or Flase)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters







    """

    ## Store initial conditions in new structure for updating ##
    NewCond = InitCond

    ## Check for germination (if in growing season) ##
    if GrowingSeason == True:
        # Find compartments covered by top soil layer affecting germination
        comp_sto = np.argwhere(prof.dzsum >= Soil_zGerm).flatten()[0]
        # Calculate water content in top soil layer
        Wr = 0
        WrFC = 0
        WrWP = 0
        for ii in range(comp_sto + 1):
            # Get soil layer
            # Determine fraction of compartment covered by top soil layer
            if prof.dzsum[ii] > Soil_zGerm:
                factor = 1 - ((prof.dzsum[ii] - Soil_zGerm) / prof.dz[ii])
            else:
                factor = 1

            # Increment actual water storage (mm)
            Wr = Wr + round(factor * 1000 * InitCond.th[ii] * prof.dz[ii], 3)
            # Increment water storage at field capacity (mm)
            WrFC = WrFC + round(factor * 1000 * prof.th_fc[ii] * prof.dz[ii], 3)
            # Increment water storage at permanent wilting point (mm)
            WrWP = WrWP + round(factor * 1000 * prof.th_wp[ii] * prof.dz[ii], 3)

        # Limit actual water storage to not be less than zero
        if Wr < 0:
            Wr = 0

        # Calculate proportional water content
        WcProp = 1 - ((WrFC - Wr) / (WrFC - WrWP))

        # Check if water content is above germination threshold
        if (WcProp >= Crop_GermThr) & (NewCond.Germination == False):
            # Crop has germinated
            NewCond.Germination = True
            # If crop sown as seedling, turn on seedling protection
            if Crop_PlantMethod == True:
                NewCond.ProtectedSeed = True
            else:
                # Crop is transplanted so no protection
                NewCond.ProtectedSeed = False

        # Increment delayed growth time counters if germination is yet to
        # occur, & also set seed protection to False if yet to germinate
        if NewCond.Germination == False:
            NewCond.DelayedCDs = InitCond.DelayedCDs + 1
            NewCond.DelayedGDDs = InitCond.DelayedGDDs + GDD
            NewCond.ProtectedSeed = False

    else:
        # Not in growing season so no germination calculation is performed.
        NewCond.Germination = False
        NewCond.ProtectedSeed = False
        NewCond.DelayedCDs = 0
        NewCond.DelayedGDDs = 0

    return NewCond


# Cell
@njit()
def growth_stage(Crop, InitCond, GrowingSeason):
    """
    Function to determine current growth stage of crop

    (used only for irrigation soil moisture thresholds)

    *Arguments:*



    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `GrowingSeason`:: `bool` : is growing season (True or Flase)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters





    """

    ## Store initial conditions in new structure for updating ##
    NewCond = InitCond

    ## Get growth stage (if in growing season) ##
    if GrowingSeason == True:
        # Adjust time for any delayed growth
        if Crop.CalendarType == 1:
            tAdj = NewCond.DAP - NewCond.DelayedCDs
        elif Crop.CalendarType == 2:
            tAdj = NewCond.GDDcum - NewCond.DelayedGDDs

        # Update growth stage
        if tAdj <= Crop.Canopy10Pct:
            NewCond.GrowthStage = 1
        elif tAdj <= Crop.MaxCanopy:
            NewCond.GrowthStage = 2
        elif tAdj <= Crop.Senescence:
            NewCond.GrowthStage = 3
        elif tAdj > Crop.Senescence:
            NewCond.GrowthStage = 4

    else:
        # Not in growing season so growth stage is set to dummy value
        NewCond.GrowthStage = 0

    return NewCond


# Cell
@njit()
def water_stress(Crop, InitCond, Dr, TAW, Et0, beta):
    """
    Function to calculate water stress coefficients

    <a href="../pdfs/ac_ref_man_3.pdf#page=18" target="_blank">Reference Manual: water stress equations</a> (pg. 9-13)


    *Arguments:*


    `Crop`: `CropClass` : Crop Object

    `InitCond`: `InitCondClass` : InitCond object

    `Dr`: `DrClass` : Depletion object (contains rootzone & top soil depletion totals)

    `TAW`: `TAWClass` : TAW object (contains rootzone & top soil total available water)

    `Et0`: `float` : Reference Evapotranspiration

    `beta`: `float` : Adjust senescence threshold if early sensescence is triggered


    *Returns:*

    `Ksw`: `KswClass` : Ksw object containint water stress coefficients





    """

    ## Calculate relative root zone water depletion for each stress type ##
    # Number of stress variables
    nstress = len(Crop.p_up)

    # Store stress thresholds
    p_up = np.ones(nstress) * Crop.p_up
    p_lo = np.ones(nstress) * Crop.p_lo
    if Crop.ETadj == 1:
        # Adjust stress thresholds for Et0 on currentbeta day (don't do this for
        # pollination water stress coefficient)

        for ii in range(3):
            p_up[ii] = p_up[ii] + (0.04 * (5 - Et0)) * (np.log10(10 - 9 * p_up[ii]))
            p_lo[ii] = p_lo[ii] + (0.04 * (5 - Et0)) * (np.log10(10 - 9 * p_lo[ii]))

    # Adjust senescence threshold if early sensescence is triggered
    if (beta == True) & (InitCond.tEarlySen > 0):
        p_up[2] = p_up[2] * (1 - Crop.beta / 100)

    # Limit values
    p_up = np.maximum(p_up, np.zeros(4))
    p_lo = np.maximum(p_lo, np.zeros(4))
    p_up = np.minimum(p_up, np.ones(4))
    p_lo = np.minimum(p_lo, np.ones(4))

    # Calculate relative depletion
    Drel = np.zeros(nstress)
    for ii in range(nstress):
        if Dr <= (p_up[ii] * TAW):
            # No water stress
            Drel[ii] = 0
        elif (Dr > (p_up[ii] * TAW)) & (Dr < (p_lo[ii] * TAW)):
            # Partial water stress
            Drel[ii] = 1 - ((p_lo[ii] - (Dr / TAW)) / (p_lo[ii] - p_up[ii]))
        elif Dr >= (p_lo[ii] * TAW):
            # Full water stress
            Drel[ii] = 1

    ## Calculate root zone water stress coefficients ##
    Ks = np.ones(3)
    for ii in range(3):
        Ks[ii] = 1 - ((np.exp(Drel[ii] * Crop.fshape_w[ii]) - 1) / (np.exp(Crop.fshape_w[ii]) - 1))

    Ksw = KswClass()

    # Water stress coefficient for leaf expansion
    Ksw.Exp = Ks[0]
    # Water stress coefficient for stomatal closure
    Ksw.Sto = Ks[1]
    # Water stress coefficient for senescence
    Ksw.Sen = Ks[2]
    # Water stress coefficient for pollination failure
    Ksw.Pol = 1 - Drel[3]
    # Mean water stress coefficient for stomatal closure
    Ksw.StoLin = 1 - Drel[1]

    return Ksw


# Cell
@njit()
def cc_development(CCo, CCx, CGC, CDC, dt, Mode, CCx0):
    """
    Function to calculate canopy cover development by end of the current simulation day

    <a href="../pdfs/ac_ref_man_3.pdf#page=30" target="_blank">Reference Manual: CC devlopment</a> (pg. 21-24)


    *Arguments:*



    `CCo`: `float` : Fractional canopy cover size at emergence

    `CCx`: `float` : Maximum canopy cover (fraction of soil cover)

    `CGC`: `float` : Canopy growth coefficient (fraction per GDD)

    `CDC`: `float` : Canopy decline coefficient (fraction per GDD/calendar day)

    `dt`: `float` : Time delta of canopy growth (1 calander day or ... GDD)

    `Mode`: `str` : Stage of Canopy developement (Growth or Decline)

    `CCx0`: `float` : Maximum canopy cover (fraction of soil cover)

    *Returns:*

    `CC`: `float` : Canopy Cover




    """

    ## Initialise output ##

    ## Calculate new canopy cover ##
    if Mode == "Growth":
        # Calculate canopy growth
        # Exponential growth stage
        CC = CCo * np.exp(CGC * dt)
        if CC > (CCx / 2):
            # Exponential decay stage
            CC = CCx - 0.25 * (CCx / CCo) * CCx * np.exp(-CGC * dt)

        # Limit CC to CCx
        if CC > CCx:
            CC = CCx

    elif Mode == "Decline":
        # Calculate canopy decline
        if CCx < 0.001:
            CC = 0
        else:
            CC = CCx * (
                1
                - 0.05
                * (np.exp(dt * CDC * 3.33 * ((CCx + 2.29) / (CCx0 + 2.29)) / (CCx + 2.29)) - 1)
            )

    ## Limit canopy cover to between 0 & 1 ##
    if CC > 1:
        CC = 1
    elif CC < 0:
        CC = 0

    return CC


# Cell
@njit()
def cc_required_time(CCprev, CCo, CCx, CGC, CDC, Mode):
    """
    Function to find time required to reach CC at end of previous day, given current CGC or CDC

    <a href="../pdfs/ac_ref_man_3.pdf#page=30" target="_blank">Reference Manual: CC devlopment</a> (pg. 21-24)



    *Arguments:*


    `CCprev`: `float` : Canopy Cover at previous timestep.

    `CCo`: `float` : Fractional canopy cover size at emergence

    `CCx`: `float` : Maximum canopy cover (fraction of soil cover)

    `CGC`: `float` : Canopy growth coefficient (fraction per GDD)

    `CDC`: `float` : Canopy decline coefficient (fraction per GDD/calendar day)

    `Mode`: `str` : Canopy growth/decline coefficient (fraction per GDD/calendar day)


    *Returns:*

    `tReq`: `float` : time required to reach CC at end of previous day





    """

    ## Get CGC &/or time (GDD or CD) required to reach CC on previous day ##
    if Mode == "CGC":
        if CCprev <= (CCx / 2):

            # print(CCprev,CCo,(tSum-dt),tSum,dt)
            CGCx = np.log(CCprev / CCo)
            # print(np.log(CCprev/CCo),(tSum-dt),CGCx)
        else:
            # print(CCx,CCo,CCprev)
            CGCx = np.log((0.25 * CCx * CCx / CCo) / (CCx - CCprev))

        tReq = CGCx / CGC

    elif Mode == "CDC":
        tReq = (np.log(1 + (1 - CCprev / CCx) / 0.05)) / (CDC / CCx)

    return tReq


# Cell
@njit()
def adjust_CCx(CCprev, CCo, CCx, CGC, CDC, dt, tSum, Crop_CanopyDevEnd, Crop_CCx):
    """
    Function to adjust CCx value for changes in CGC due to water stress during the growing season

    <a href="../pdfs/ac_ref_man_3.pdf#page=36" target="_blank">Reference Manual: CC stress response</a> (pg. 27-33)


    *Arguments:*


    `CCprev`: `float` : Canopy Cover at previous timestep.

    `CCo`: `float` : Fractional canopy cover size at emergence

    `CCx`: `float` : Maximum canopy cover (fraction of soil cover)

    `CGC`: `float` : Canopy growth coefficient (fraction per GDD)

    `CDC`: `float` : Canopy decline coefficient (fraction per GDD/calendar day)

    `dt`: `float` : Time delta of canopy growth (1 calander day or ... GDD)

    `tSum`: `float` : time since germination (CD or GDD)

    `Crop_CanopyDevEnd`: `float` : time that Canopy developement ends

    `Crop_CCx`: `float` : Maximum canopy cover (fraction of soil cover)

    *Returns:*

    `CCxAdj`: `float` : Adjusted CCx





    """

    ## Get time required to reach CC on previous day ##
    tCCtmp = cc_required_time(CCprev, CCo, CCx, CGC, CDC, "CGC")

    ## Determine CCx adjusted ##
    if tCCtmp > 0:
        tCCtmp = tCCtmp + (Crop_CanopyDevEnd - tSum) + dt
        CCxAdj = cc_development(CCo, CCx, CGC, CDC, tCCtmp, "Growth", Crop_CCx)
    else:
        CCxAdj = 0

    return CCxAdj


# Cell
@njit()
def update_CCx_CDC(CCprev, CDC, CCx, dt):
    """
    Function to update CCx & CDC parameter valyes for rewatering in late season of an early declining canopy

    <a href="../pdfs/ac_ref_man_3.pdf#page=36" target="_blank">Reference Manual: CC stress response</a> (pg. 27-33)


    *Arguments:*


    `CCprev`: `float` : Canopy Cover at previous timestep.

    `CDC`: `float` : Canopy decline coefficient (fraction per GDD/calendar day)

    `CCx`: `float` : Maximum canopy cover (fraction of soil cover)

    `dt`: `float` : Time delta of canopy growth (1 calander day or ... GDD)


    *Returns:*

    `CCxAdj`: `float` : updated CCxAdj

    `CDCadj`: `float` : updated CDCadj





    """

    ## Get adjusted CCx ##
    CCXadj = CCprev / (1 - 0.05 * (np.exp(dt * ((CDC * 3.33) / (CCx + 2.29))) - 1))

    ## Get adjusted CDC ##
    CDCadj = CDC * ((CCXadj + 2.29) / (CCx + 2.29))

    return CCXadj, CDCadj


# Cell
@njit()
def canopy_cover(Crop, Soil_Profile, Soil_zTop, InitCond, GDD, Et0, GrowingSeason):
    # def canopy_cover(Crop,Soil_Profile,Soil_zTop,InitCond,GDD,Et0,GrowingSeason):

    """
    Function to simulate canopy growth/decline

    <a href="../pdfs/ac_ref_man_3.pdf#page=30" target="_blank">Reference Manual: CC equations</a> (pg. 21-33)


    *Arguments:*


    `Crop`: `CropClass` : Crop object

    `Soil_Profile`: `SoilProfileClass` : Soil object

    `Soil_zTop`: `float` : top soil depth

    `InitCond`: `InitCondClass` : InitCond object

    `GDD`: `float` : Growing Degree Days

    `Et0`: `float` : reference evapotranspiration

    `GrowingSeason`:: `bool` : is it currently within the growing season (True, Flase)

    *Returns:*


    `NewCond`: `InitCondClass` : updated InitCond object


    """

    # Function to simulate canopy growth/decline

    InitCond_CC_NS = InitCond.CC_NS
    InitCond_CC = InitCond.CC
    InitCond_ProtectedSeed = InitCond.ProtectedSeed
    InitCond_CCxAct = InitCond.CCxAct
    InitCond_CropDead = InitCond.CropDead
    InitCond_tEarlySen = InitCond.tEarlySen
    InitCond_CCxW = InitCond.CCxW

    ## Store initial conditions in a new structure for updating ##
    NewCond = InitCond
    NewCond.CCprev = InitCond.CC

    ## Calculate canopy development (if in growing season) ##
    if GrowingSeason == True:
        # Calculate root zone water content
        _, Dr, TAW, _ = root_zone_water(
            Soil_Profile, float(NewCond.Zroot), NewCond.th, Soil_zTop, float(Crop.Zmin), Crop.Aer
        )
        # Check whether to use root zone or top soil depletions for calculating
        # water stress
        if (Dr.Rz / TAW.Rz) <= (Dr.Zt / TAW.Zt):
            # Root zone is wetter than top soil, so use root zone value
            Dr = Dr.Rz
            TAW = TAW.Rz
        else:
            # Top soil is wetter than root zone, so use top soil values
            Dr = Dr.Zt
            TAW = TAW.Zt

        # Determine if water stress is occurring
        beta = True
        Ksw = water_stress(Crop, NewCond, Dr, TAW, Et0, beta)
        # Get canopy cover growth time
        if Crop.CalendarType == 1:
            dtCC = 1
            tCCadj = NewCond.DAP - NewCond.DelayedCDs
        elif Crop.CalendarType == 2:
            dtCC = GDD
            tCCadj = NewCond.GDDcum - NewCond.DelayedGDDs

        ## Canopy development (potential) ##
        if (tCCadj < Crop.Emergence) or (round(tCCadj) > Crop.Maturity):
            # No canopy development before emergence/germination or after
            # maturity
            NewCond.CC_NS = 0
        elif tCCadj < Crop.CanopyDevEnd:
            # Canopy growth can occur
            if InitCond_CC_NS <= Crop.CC0:
                # Very small initial CC.
                NewCond.CC_NS = Crop.CC0 * np.exp(Crop.CGC * dtCC)
                # print(Crop.CC0,np.exp(Crop.CGC*dtCC))
            else:
                # Canopy growing
                tmp_tCC = tCCadj - Crop.Emergence
                NewCond.CC_NS = cc_development(
                    Crop.CC0, 0.98 * Crop.CCx, Crop.CGC, Crop.CDC, tmp_tCC, "Growth", Crop.CCx
                )

            # Update maximum canopy cover size in growing season
            NewCond.CCxAct_NS = NewCond.CC_NS
        elif tCCadj > Crop.CanopyDevEnd:
            # No more canopy growth is possible or canopy in decline
            # Set CCx for calculation of withered canopy effects
            NewCond.CCxW_NS = NewCond.CCxAct_NS
            if tCCadj < Crop.Senescence:
                # Mid-season stage - no canopy growth
                NewCond.CC_NS = InitCond_CC_NS
                # Update maximum canopy cover size in growing season
                NewCond.CCxAct_NS = NewCond.CC_NS
            else:
                # Late-season stage - canopy decline
                tmp_tCC = tCCadj - Crop.Senescence
                NewCond.CC_NS = cc_development(
                    Crop.CC0,
                    NewCond.CCxAct_NS,
                    Crop.CGC,
                    Crop.CDC,
                    tmp_tCC,
                    "Decline",
                    NewCond.CCxAct_NS,
                )

        ## Canopy development (actual) ##
        if (tCCadj < Crop.Emergence) or (round(tCCadj) > Crop.Maturity):
            # No canopy development before emergence/germination or after
            # maturity
            NewCond.CC = 0
            NewCond.CC0adj = Crop.CC0
        elif tCCadj < Crop.CanopyDevEnd:
            # Canopy growth can occur
            if InitCond_CC <= NewCond.CC0adj or (
                (InitCond_ProtectedSeed == True) & (InitCond_CC <= (1.25 * NewCond.CC0adj))
            ):
                # Very small initial CC or seedling in protected phase of
                # growth. In this case, assume no leaf water expansion stress
                if InitCond_ProtectedSeed == True:
                    tmp_tCC = tCCadj - Crop.Emergence
                    NewCond.CC = cc_development(
                        Crop.CC0, Crop.CCx, Crop.CGC, Crop.CDC, tmp_tCC, "Growth", Crop.CCx
                    )
                    # Check if seed protection should be turned off
                    if NewCond.CC > (1.25 * NewCond.CC0adj):
                        # Turn off seed protection - lead expansion stress can
                        # occur on future time steps.
                        NewCond.ProtectedSeed = False

                else:
                    NewCond.CC = NewCond.CC0adj * np.exp(Crop.CGC * dtCC)

            else:
                # Canopy growing

                if InitCond_CC < (0.9799 * Crop.CCx):
                    # Adjust canopy growth coefficient for leaf expansion water
                    # stress effects
                    CGCadj = Crop.CGC * Ksw.Exp
                    if CGCadj > 0:

                        # Adjust CCx for change in CGC
                        CCXadj = adjust_CCx(
                            InitCond_CC,
                            NewCond.CC0adj,
                            Crop.CCx,
                            CGCadj,
                            Crop.CDC,
                            dtCC,
                            tCCadj,
                            Crop.CanopyDevEnd,
                            Crop.CCx,
                        )
                        if CCXadj < 0:

                            NewCond.CC = InitCond_CC
                        elif abs(InitCond_CC - (0.9799 * Crop.CCx)) < 0.001:

                            # Approaching maximum canopy cover size
                            tmp_tCC = tCCadj - Crop.Emergence
                            NewCond.CC = cc_development(
                                Crop.CC0, Crop.CCx, Crop.CGC, Crop.CDC, tmp_tCC, "Growth", Crop.CCx
                            )
                        else:

                            # Determine time required to reach CC on previous,
                            # day, given CGCAdj value
                            tReq = cc_required_time(
                                InitCond_CC, NewCond.CC0adj, CCXadj, CGCadj, Crop.CDC, "CGC"
                            )
                            if tReq > 0:

                                # Calclate GDD's for canopy growth
                                tmp_tCC = tReq + dtCC
                                # Determine new canopy size
                                NewCond.CC = cc_development(
                                    NewCond.CC0adj,
                                    CCXadj,
                                    CGCadj,
                                    Crop.CDC,
                                    tmp_tCC,
                                    "Growth",
                                    Crop.CCx,
                                )
                                # print(NewCond.DAP,CCXadj,tReq)

                            else:
                                # No canopy growth
                                NewCond.CC = InitCond_CC

                    else:

                        # No canopy growth
                        NewCond.CC = InitCond_CC
                        # Update CC0
                        if NewCond.CC > NewCond.CC0adj:
                            NewCond.CC0adj = Crop.CC0
                        else:
                            NewCond.CC0adj = NewCond.CC

                else:
                    # Canopy approaching maximum size
                    tmp_tCC = tCCadj - Crop.Emergence
                    NewCond.CC = cc_development(
                        Crop.CC0, Crop.CCx, Crop.CGC, Crop.CDC, tmp_tCC, "Growth", Crop.CCx
                    )
                    NewCond.CC0adj = Crop.CC0

            if NewCond.CC > InitCond_CCxAct:
                # Update actual maximum canopy cover size during growing season
                NewCond.CCxAct = NewCond.CC

        elif tCCadj > Crop.CanopyDevEnd:

            # No more canopy growth is possible or canopy is in decline
            if tCCadj < Crop.Senescence:
                # Mid-season stage - no canopy growth
                NewCond.CC = InitCond_CC
                if NewCond.CC > InitCond_CCxAct:
                    # Update actual maximum canopy cover size during growing
                    # season
                    NewCond.CCxAct = NewCond.CC

            else:
                # Late-season stage - canopy decline
                # Adjust canopy decline coefficient for difference between actual
                # & potential CCx
                CDCadj = Crop.CDC * ((NewCond.CCxAct + 2.29) / (Crop.CCx + 2.29))
                # Determine new canopy size
                tmp_tCC = tCCadj - Crop.Senescence
                NewCond.CC = cc_development(
                    NewCond.CC0adj,
                    NewCond.CCxAct,
                    Crop.CGC,
                    CDCadj,
                    tmp_tCC,
                    "Decline",
                    NewCond.CCxAct,
                )

            # Check for crop growth termination
            if (NewCond.CC < 0.001) & (InitCond_CropDead == False):
                # Crop has died
                NewCond.CC = 0
                NewCond.CropDead = True

        ## Canopy senescence due to water stress (actual) ##
        if tCCadj >= Crop.Emergence:
            if (tCCadj < Crop.Senescence) or (InitCond_tEarlySen > 0):
                # Check for early canopy senescence  due to severe water
                # stress.
                if (Ksw.Sen < 1) & (InitCond_ProtectedSeed == False):

                    # Early canopy senescence
                    NewCond.PrematSenes = True
                    if InitCond_tEarlySen == 0:
                        # No prior early senescence
                        NewCond.CCxEarlySen = InitCond_CC

                    # Increment early senescence GDD counter
                    NewCond.tEarlySen = InitCond_tEarlySen + dtCC
                    # Adjust canopy decline coefficient for water stress
                    beta = False
                    Ksw = water_stress(Crop, NewCond, Dr, TAW, Et0, beta)
                    if Ksw.Sen > 0.99999:
                        CDCadj = 0.0001
                    else:
                        CDCadj = (1 - (Ksw.Sen ** 8)) * Crop.CDC

                    # Get new canpy cover size after senescence
                    if NewCond.CCxEarlySen < 0.001:
                        CCsen = 0
                    else:
                        # Get time required to reach CC at end of previous day, given
                        # CDCadj
                        tReq = (np.log(1 + (1 - InitCond_CC / NewCond.CCxEarlySen) / 0.05)) / (
                            (CDCadj * 3.33) / (NewCond.CCxEarlySen + 2.29)
                        )
                        # Calculate GDD's for canopy decline
                        tmp_tCC = tReq + dtCC
                        # Determine new canopy size
                        CCsen = NewCond.CCxEarlySen * (
                            1
                            - 0.05
                            * (
                                np.exp(tmp_tCC * ((CDCadj * 3.33) / (NewCond.CCxEarlySen + 2.29)))
                                - 1
                            )
                        )
                        if CCsen < 0:
                            CCsen = 0

                    # Update canopy cover size
                    if tCCadj < Crop.Senescence:
                        # Limit CC to CCx
                        if CCsen > Crop.CCx:
                            CCsen = Crop.CCx

                        # CC cannot be greater than value on previous day
                        NewCond.CC = CCsen
                        if NewCond.CC > InitCond_CC:
                            NewCond.CC = InitCond_CC

                        # Update maximum canopy cover size during growing
                        # season
                        NewCond.CCxAct = NewCond.CC
                        # Update CC0 if current CC is less than initial canopy
                        # cover size at planting
                        if NewCond.CC < Crop.CC0:
                            NewCond.CC0adj = NewCond.CC
                        else:
                            NewCond.CC0adj = Crop.CC0

                    else:
                        # Update CC to account for canopy cover senescence due
                        # to water stress
                        if CCsen < NewCond.CC:
                            NewCond.CC = CCsen

                    # Check for crop growth termination
                    if (NewCond.CC < 0.001) & (InitCond_CropDead == False):
                        # Crop has died
                        NewCond.CC = 0
                        NewCond.CropDead = True

                else:
                    # No water stress
                    NewCond.PrematSenes = False
                    if (tCCadj > Crop.Senescence) & (InitCond_tEarlySen > 0):
                        # Rewatering of canopy in late season
                        # Get new values for CCx & CDC
                        tmp_tCC = tCCadj - dtCC - Crop.Senescence
                        CCXadj, CDCadj = update_CCx_CDC(InitCond_CC, Crop.CDC, Crop.CCx, tmp_tCC)
                        NewCond.CCxAct = CCXadj
                        # Get new CC value for end of current day
                        tmp_tCC = tCCadj - Crop.Senescence
                        NewCond.CC = cc_development(
                            NewCond.CC0adj, CCXadj, Crop.CGC, CDCadj, tmp_tCC, "Decline", CCXadj
                        )
                        # Check for crop growth termination
                        if (NewCond.CC < 0.001) & (InitCond_CropDead == False):
                            NewCond.CC = 0
                            NewCond.CropDead = True

                    # Reset early senescence counter
                    NewCond.tEarlySen = 0

                # Adjust CCx for effects of withered canopy
                if NewCond.CC > InitCond_CCxW:
                    NewCond.CCxW = NewCond.CC

        ## Calculate canopy size adjusted for micro-advective effects ##
        # Check to ensure potential CC is not slightly lower than actual
        if NewCond.CC_NS < NewCond.CC:
            NewCond.CC_NS = NewCond.CC
            if tCCadj < Crop.CanopyDevEnd:
                NewCond.CCxAct_NS = NewCond.CC_NS

        # Actual (with water stress)
        NewCond.CCadj = (1.72 * NewCond.CC) - (NewCond.CC ** 2) + (0.3 * (NewCond.CC ** 3))
        # Potential (without water stress)
        NewCond.CCadj_NS = (
            (1.72 * NewCond.CC_NS) - (NewCond.CC_NS ** 2) + (0.3 * (NewCond.CC_NS ** 3))
        )

    else:
        # No canopy outside growing season - set various values to zero
        NewCond.CC = 0
        NewCond.CCadj = 0
        NewCond.CC_NS = 0
        NewCond.CCadj_NS = 0
        NewCond.CCxW = 0
        NewCond.CCxAct = 0
        NewCond.CCxW_NS = 0
        NewCond.CCxAct_NS = 0

    return NewCond


# Cell
@njit()
def evap_layer_water_content(InitCond_th, InitCond_EvapZ, prof):
    """
    Function to get water contents in the evaporation layer

    <a href="../pdfs/ac_ref_man_3.pdf#page=82" target="_blank">Reference Manual: evaporation equations</a> (pg. 73-81)


    *Arguments:*



    `InitCond_th`: `np.array` : Initial water content

    `InitCond_EvapZ`: `float` : evaporation depth

    `prof`: `SoilProfileClass` : Soil object containing soil paramaters


    *Returns:*


    `Wevap_Sat`: `float` : Water storage in evaporation layer at saturation (mm)

    `Wevap_Fc`: `float` : Water storage in evaporation layer at field capacity (mm)

    `Wevap_Wp`: `float` : Water storage in evaporation layer at permanent wilting point (mm)

    `Wevap_Dry`: `float` : Water storage in evaporation layer at air dry (mm)

    `Wevap_Act`: `float` : Actual water storage in evaporation layer (mm)



    """

    # Find soil compartments covered by evaporation layer
    comp_sto = np.sum(prof.dzsum < InitCond_EvapZ) + 1

    Wevap_Sat = 0
    Wevap_Fc = 0
    Wevap_Wp = 0
    Wevap_Dry = 0
    Wevap_Act = 0

    for ii in range(int(comp_sto)):

        # Determine fraction of soil compartment covered by evaporation layer
        if prof.dzsum[ii] > InitCond_EvapZ:
            factor = 1 - ((prof.dzsum[ii] - InitCond_EvapZ) / prof.dz[ii])
        else:
            factor = 1

        # Actual water storage in evaporation layer (mm)
        Wevap_Act += factor * 1000 * InitCond_th[ii] * prof.dz[ii]
        # Water storage in evaporation layer at saturation (mm)
        Wevap_Sat += factor * 1000 * prof.th_s[ii] * prof.dz[ii]
        # Water storage in evaporation layer at field capacity (mm)
        Wevap_Fc += factor * 1000 * prof.th_fc[ii] * prof.dz[ii]
        # Water storage in evaporation layer at permanent wilting point (mm)
        Wevap_Wp += factor * 1000 * prof.th_wp[ii] * prof.dz[ii]
        # Water storage in evaporation layer at air dry (mm)
        Wevap_Dry += factor * 1000 * prof.th_dry[ii] * prof.dz[ii]

    if Wevap_Act < 0:
        Wevap_Act = 0

    return Wevap_Sat, Wevap_Fc, Wevap_Wp, Wevap_Dry, Wevap_Act


# Cell
@njit()
def soil_evaporation(
    ClockStruct_EvapTimeSteps,
    ClockStruct_SimOffSeason,
    ClockStruct_TimeStepCounter,
    Soil_EvapZmin,
    Soil_EvapZmax,
    Soil_Profile,
    Soil_REW,
    Soil_Kex,
    Soil_fwcc,
    Soil_fWrelExp,
    Soil_fevap,
    Crop_CalendarType,
    Crop_Senescence,
    IrrMngt_IrrMethod,
    IrrMngt_WetSurf,
    FieldMngt,
    InitCond,
    Et0,
    Infl,
    Rain,
    Irr,
    GrowingSeason,
):

    """
    Function to calculate daily soil evaporation

    <a href="../pdfs/ac_ref_man_3.pdf#page=82" target="_blank">Reference Manual: evaporation equations</a> (pg. 73-81)


    *Arguments:*



    `Clock params`: `bool, int` : clock params

    `Soil parameters`: `float` : soil parameters

    `Crop params`: `float` : Crop paramaters

    `IrrMngt params`: `int, float`: irrigation management paramaters

    `FieldMngt`: `FieldMngtStruct` : Field management paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Et0`: `float` : daily reference evapotranspiration

    `Infl`: `float` : Infiltration on current day

    `Rain`: `float` : daily precipitation mm

    `Irr`: `float` : Irrigation applied on current day

    `GrowingSeason`:: `bool` : is growing season (True or Flase)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `EsAct`: `float` : Actual surface evaporation current day

    `EsPot`: `float` : Potential surface evaporation current day





    """

    Wevap = WevapClass()

    ## Store initial conditions in new structure that will be updated ##
    NewCond = InitCond

    ## Prepare stage 2 evaporation (REW gone) ##
    # Only do this if it is first day of simulation, or if it is first day of
    # growing season & not simulating off-season
    if (ClockStruct_TimeStepCounter == 0) or (
        (NewCond.DAP == 1) & (ClockStruct_SimOffSeason == False)
    ):
        # Reset storage in surface soil layer to zero
        NewCond.Wsurf = 0
        # Set evaporation depth to minimum
        NewCond.EvapZ = Soil_EvapZmin
        # Trigger stage 2 evaporation
        NewCond.Stage2 = True
        # Get relative water content for start of stage 2 evaporation
        Wevap.Sat, Wevap.Fc, Wevap.Wp, Wevap.Dry, Wevap.Act = evap_layer_water_content(
            NewCond.th, NewCond.EvapZ, Soil_Profile
        )
        NewCond.Wstage2 = round(
            (Wevap.Act - (Wevap.Fc - Soil_REW)) / (Wevap.Sat - (Wevap.Fc - Soil_REW)), 2
        )
        if NewCond.Wstage2 < 0:
            NewCond.Wstage2 = 0

    ## Prepare soil evaporation stage 1 ##
    # Adjust water in surface evaporation layer for any infiltration
    if (Rain > 0) or ((Irr > 0) & (IrrMngt_IrrMethod != 4)):
        # Only prepare stage one when rainfall occurs, or when irrigation is
        # trigerred (not in net irrigation mode)
        if Infl > 0:
            # Update storage in surface evaporation layer for incoming
            # infiltration
            NewCond.Wsurf = Infl
            # Water stored in surface evaporation layer cannot exceed REW
            if NewCond.Wsurf > Soil_REW:
                NewCond.Wsurf = Soil_REW

            # Reset variables
            NewCond.Wstage2 = 0
            NewCond.EvapZ = Soil_EvapZmin
            NewCond.Stage2 = False

    ## Calculate potential soil evaporation rate (mm/day) ##
    if GrowingSeason == True:
        # Adjust time for any delayed development
        if Crop_CalendarType == 1:
            tAdj = NewCond.DAP - NewCond.DelayedCDs
        elif Crop_CalendarType == 2:
            tAdj = NewCond.GDDcum - NewCond.DelayedGDDs

        # Calculate maximum potential soil evaporation
        EsPotMax = Soil_Kex * Et0 * (1 - NewCond.CCxW * (Soil_fwcc / 100))
        # Calculate potential soil evaporation (given current canopy cover
        # size)
        EsPot = Soil_Kex * (1 - NewCond.CCadj) * Et0

        # Adjust potential soil evaporation for effects of withered canopy
        if (tAdj > Crop_Senescence) & (NewCond.CCxAct > 0):
            if NewCond.CC > (NewCond.CCxAct / 2):
                if NewCond.CC > NewCond.CCxAct:
                    mult = 0
                else:
                    mult = (NewCond.CCxAct - NewCond.CC) / (NewCond.CCxAct / 2)

            else:
                mult = 1

            EsPot = EsPot * (1 - NewCond.CCxAct * (Soil_fwcc / 100) * mult)
            CCxActAdj = (
                (1.72 * NewCond.CCxAct) - (NewCond.CCxAct ** 2) + 0.3 * (NewCond.CCxAct ** 3)
            )
            EsPotMin = Soil_Kex * (1 - CCxActAdj) * Et0
            if EsPotMin < 0:
                EsPotMin = 0

            if EsPot < EsPotMin:
                EsPot = EsPotMin
            elif EsPot > EsPotMax:
                EsPot = EsPotMax

        if NewCond.PrematSenes == True:
            if EsPot > EsPotMax:
                EsPot = EsPotMax

    else:
        # No canopy cover outside of growing season so potential soil
        # evaporation only depends on reference evapotranspiration
        EsPot = Soil_Kex * Et0

    ## Adjust potential soil evaporation for mulches &/or partial wetting ##
    # Mulches
    if NewCond.SurfaceStorage < 0.000001:
        if not FieldMngt.Mulches:
            # No mulches present
            EsPotMul = EsPot
        elif FieldMngt.Mulches:
            # Mulches present
            EsPotMul = EsPot * (1 - FieldMngt.fMulch * (FieldMngt.MulchPct / 100))

    else:
        # Surface is flooded - no adjustment of potential soil evaporation for
        # mulches
        EsPotMul = EsPot

    # Partial surface wetting by irrigation
    if (Irr > 0) & (IrrMngt_IrrMethod != 4):
        # Only apply adjustment if irrigation occurs & not in net irrigation
        # mode
        if (Rain > 1) or (NewCond.SurfaceStorage > 0):
            # No adjustment for partial wetting - assume surface is fully wet
            EsPotIrr = EsPot
        else:
            # Adjust for proprtion of surface area wetted by irrigation
            EsPotIrr = EsPot * (IrrMngt_WetSurf / 100)

    else:
        # No adjustment for partial surface wetting
        EsPotIrr = EsPot

    # Assign minimum value (mulches & partial wetting don't combine)
    EsPot = min(EsPotIrr, EsPotMul)

    ## Surface evaporation ##
    # Initialise actual evaporation counter
    EsAct = 0
    # Evaporate surface storage
    if NewCond.SurfaceStorage > 0:
        if NewCond.SurfaceStorage > EsPot:
            # All potential soil evaporation can be supplied by surface storage
            EsAct = EsPot
            # Update surface storage
            NewCond.SurfaceStorage = NewCond.SurfaceStorage - EsAct
        else:
            # Surface storage is not sufficient to meet all potential soil
            # evaporation
            EsAct = NewCond.SurfaceStorage
            # Update surface storage, evaporation layer depth, stage
            NewCond.SurfaceStorage = 0
            NewCond.Wsurf = Soil_REW
            NewCond.Wstage2 = 0
            NewCond.EvapZ = Soil_EvapZmin
            NewCond.Stage2 = False

    ## Stage 1 evaporation ##
    # Determine total water to be extracted
    ToExtract = EsPot - EsAct
    # Determine total water to be extracted in stage one (limited by surface
    # layer water storage)
    ExtractPotStg1 = min(ToExtract, NewCond.Wsurf)
    # Extract water
    if ExtractPotStg1 > 0:
        # Find soil compartments covered by evaporation layer
        comp_sto = np.sum(Soil_Profile.dzsum < Soil_EvapZmin) + 1
        comp = -1
        prof = Soil_Profile
        while (ExtractPotStg1 > 0) & (comp < comp_sto):
            # Increment compartment counter
            comp = comp + 1
            # Specify layer number
            # Determine proportion of compartment in evaporation layer
            if prof.dzsum[comp] > Soil_EvapZmin:
                factor = 1 - ((prof.dzsum[comp] - Soil_EvapZmin) / prof.dz[comp])
            else:
                factor = 1

            # Water storage (mm) at air dry
            Wdry = 1000 * prof.th_dry[comp] * prof.dz[comp]
            # Available water (mm)
            W = 1000 * NewCond.th[comp] * prof.dz[comp]
            # Water available in compartment for extraction (mm)
            AvW = (W - Wdry) * factor
            if AvW < 0:
                AvW = 0

            if AvW >= ExtractPotStg1:
                # Update actual evaporation
                EsAct = EsAct + ExtractPotStg1
                # Update depth of water in current compartment
                W = W - ExtractPotStg1
                # Update total water to be extracted
                ToExtract = ToExtract - ExtractPotStg1
                # Update water to be extracted from surface layer (stage 1)
                ExtractPotStg1 = 0
            else:
                # Update actual evaporation
                EsAct = EsAct + AvW
                # Update water to be extracted from surface layer (stage 1)
                ExtractPotStg1 = ExtractPotStg1 - AvW
                # Update total water to be extracted
                ToExtract = ToExtract - AvW
                # Update depth of water in current compartment
                W = W - AvW

            # Update water content
            NewCond.th[comp] = W / (1000 * prof.dz[comp])

        # Update surface evaporation layer water balance
        NewCond.Wsurf = NewCond.Wsurf - EsAct
        if (NewCond.Wsurf < 0) or (ExtractPotStg1 > 0.0001):
            NewCond.Wsurf = 0

        # If surface storage completely depleted, prepare stage 2
        if NewCond.Wsurf < 0.0001:
            # Get water contents (mm)
            Wevap.Sat, Wevap.Fc, Wevap.Wp, Wevap.Dry, Wevap.Act = evap_layer_water_content(
                NewCond.th, NewCond.EvapZ, Soil_Profile
            )
            # Proportional water storage for start of stage two evaporation
            NewCond.Wstage2 = round(
                (Wevap.Act - (Wevap.Fc - Soil_REW)) / (Wevap.Sat - (Wevap.Fc - Soil_REW)), 2
            )
            if NewCond.Wstage2 < 0:
                NewCond.Wstage2 = 0

    ## Stage 2 evaporation ##
    # Extract water
    if ToExtract > 0:
        # Start stage 2
        NewCond.Stage2 = True
        # Get sub-daily evaporative demand
        Edt = ToExtract / ClockStruct_EvapTimeSteps
        # Loop sub-daily steps
        for jj in range(int(ClockStruct_EvapTimeSteps)):
            # Get current water storage (mm)
            Wevap.Sat, Wevap.Fc, Wevap.Wp, Wevap.Dry, Wevap.Act = evap_layer_water_content(
                NewCond.th, NewCond.EvapZ, Soil_Profile
            )
            # Get water storage (mm) at start of stage 2 evaporation
            Wupper = NewCond.Wstage2 * (Wevap.Sat - (Wevap.Fc - Soil_REW)) + (Wevap.Fc - Soil_REW)
            # Get water storage (mm) when there is no evaporation
            Wlower = Wevap.Dry
            # Get relative depletion of evaporation storage in stage 2
            Wrel = (Wevap.Act - Wlower) / (Wupper - Wlower)
            # Check if need to expand evaporation layer
            if Soil_EvapZmax > Soil_EvapZmin:
                Wcheck = Soil_fWrelExp * (
                    (Soil_EvapZmax - NewCond.EvapZ) / (Soil_EvapZmax - Soil_EvapZmin)
                )
                while (Wrel < Wcheck) & (NewCond.EvapZ < Soil_EvapZmax):
                    # Expand evaporation layer by 1 mm
                    NewCond.EvapZ = NewCond.EvapZ + 0.001
                    # Update water storage (mm) in evaporation layer
                    Wevap.Sat, Wevap.Fc, Wevap.Wp, Wevap.Dry, Wevap.Act = evap_layer_water_content(
                        NewCond.th, NewCond.EvapZ, Soil_Profile
                    )
                    Wupper = NewCond.Wstage2 * (Wevap.Sat - (Wevap.Fc - Soil_REW)) + (
                        Wevap.Fc - Soil_REW
                    )
                    Wlower = Wevap.Dry
                    # Update relative depletion of evaporation storage
                    Wrel = (Wevap.Act - Wlower) / (Wupper - Wlower)
                    Wcheck = Soil_fWrelExp * (
                        (Soil_EvapZmax - NewCond.EvapZ) / (Soil_EvapZmax - Soil_EvapZmin)
                    )

            # Get stage 2 evaporation reduction coefficient
            Kr = (np.exp(Soil_fevap * Wrel) - 1) / (np.exp(Soil_fevap) - 1)
            if Kr > 1:
                Kr = 1

            # Get water to extract (mm)
            ToExtractStg2 = Kr * Edt

            # Extract water from compartments
            comp_sto = np.sum(Soil_Profile.dzsum < NewCond.EvapZ) + 1
            comp = -1
            prof = Soil_Profile
            while (ToExtractStg2 > 0) & (comp < comp_sto):
                # Increment compartment counter
                comp = comp + 1
                # Specify layer number
                # Determine proportion of compartment in evaporation layer
                if prof.dzsum[comp] > NewCond.EvapZ:
                    factor = 1 - ((prof.dzsum[comp] - NewCond.EvapZ) / prof.dz[comp])
                else:
                    factor = 1

                # Water storage (mm) at air dry
                Wdry = 1000 * prof.th_dry[comp] * prof.dz[comp]
                # Available water (mm)
                W = 1000 * NewCond.th[comp] * prof.dz[comp]
                # Water available in compartment for extraction (mm)
                AvW = (W - Wdry) * factor
                if AvW >= ToExtractStg2:
                    # Update actual evaporation
                    EsAct = EsAct + ToExtractStg2
                    # Update depth of water in current compartment
                    W = W - ToExtractStg2
                    # Update total water to be extracted
                    ToExtract = ToExtract - ToExtractStg2
                    # Update water to be extracted from surface layer (stage 1)
                    ToExtractStg2 = 0
                else:
                    # Update actual evaporation
                    EsAct = EsAct + AvW
                    # Update depth of water in current compartment
                    W = W - AvW
                    # Update water to be extracted from surface layer (stage 1)
                    ToExtractStg2 = ToExtractStg2 - AvW
                    # Update total water to be extracted
                    ToExtract = ToExtract - AvW

                # Update water content
                NewCond.th[comp] = W / (1000 * prof.dz[comp])

    ## Store potential evaporation for irrigation calculations on next day ##
    NewCond.Epot = EsPot

    return NewCond, EsAct, EsPot


# Cell
@njit()
def aeration_stress(NewCond_AerDays, Crop_LagAer, thRZ):
    """
    Function to calculate aeration stress coefficient

    <a href="../pdfs/ac_ref_man_3.pdf#page=90" target="_blank">Reference Manual: aeration stress</a> (pg. 89-90)


    *Arguments:*


    `NewCond_AerDays`: `int` : number aeration stress days

    `Crop_LagAer`: `int` : lag days before aeration stress

    `thRZ`: `thRZClass` : object that contains information on the total water in the root zone



    *Returns:*

    `Ksa_Aer`: `float` : aeration stress coefficient

    `NewCond_AerDays`: `float` : updated aer days



    """

    ## Determine aeration stress (root zone) ##
    if thRZ.Act > thRZ.Aer:
        # Calculate aeration stress coefficient
        if NewCond_AerDays < Crop_LagAer:
            stress = 1 - ((thRZ.S - thRZ.Act) / (thRZ.S - thRZ.Aer))
            Ksa_Aer = 1 - ((NewCond_AerDays / 3) * stress)
        elif NewCond_AerDays >= Crop_LagAer:
            Ksa_Aer = (thRZ.S - thRZ.Act) / (thRZ.S - thRZ.Aer)

        # Increment aeration days counter
        NewCond_AerDays = NewCond_AerDays + 1
        if NewCond_AerDays > Crop_LagAer:
            NewCond_AerDays = Crop_LagAer

    else:
        # Set aeration stress coefficient to one (no stress value)
        Ksa_Aer = 1
        # Reset aeration days counter
        NewCond_AerDays = 0

    return Ksa_Aer, NewCond_AerDays


# Cell
@njit()
def transpiration(
    Soil_Profile,
    Soil_nComp,
    Soil_zTop,
    Crop,
    IrrMngt_IrrMethod,
    IrrMngt_NetIrrSMT,
    InitCond,
    Et0,
    CO2,
    GrowingSeason,
    GDD,
):

    """
    Function to calculate crop transpiration on current day

    <a href="../pdfs/ac_ref_man_3.pdf#page=91" target="_blank">Reference Manual: transpiration equations</a> (pg. 82-91)



    *Arguments:*


    `Soil`: `SoilClass` : Soil object

    `Crop`: `CropClass` : Crop object

    `IrrMngt`: `IrrMngt`: object containing irrigation management params

    `InitCond`: `InitCondClass` : InitCond object

    `Et0`: `float` : reference evapotranspiration

    `CO2`: `CO2class` : CO2

    `GDD`: `float` : Growing Degree Days

    `GrowingSeason`:: `bool` : is it currently within the growing season (True, Flase)

    *Returns:*


    `TrAct`: `float` : Actual Transpiration on current day

    `TrPot_NS`: `float` : Potential Transpiration on current day with no water stress

    `TrPot0`: `float` : Potential Transpiration on current day

    `NewCond`: `InitCondClass` : updated InitCond object

    `IrrNet`: `float` : Net Irrigation (if required)







    """

    ## Store initial conditions ##
    NewCond = InitCond

    InitCond_th = InitCond.th

    prof = Soil_Profile

    ## Calculate transpiration (if in growing season) ##
    if GrowingSeason == True:
        ## Calculate potential transpiration ##
        # 1. No prior water stress
        # Update ageing days counter
        DAPadj = NewCond.DAP - NewCond.DelayedCDs
        if DAPadj > Crop.MaxCanopyCD:
            NewCond.AgeDays_NS = DAPadj - Crop.MaxCanopyCD

        # Update crop coefficient for ageing of canopy
        if NewCond.AgeDays_NS > 5:
            Kcb_NS = Crop.Kcb - ((NewCond.AgeDays_NS - 5) * (Crop.fage / 100)) * NewCond.CCxW_NS
        else:
            Kcb_NS = Crop.Kcb

        # Update crop coefficient for CO2 concentration
        CO2CurrentConc = CO2.CurrentConc
        CO2RefConc = CO2.RefConc
        if CO2CurrentConc > CO2RefConc:
            Kcb_NS = Kcb_NS * (1 - 0.05 * ((CO2CurrentConc - CO2RefConc) / (550 - CO2RefConc)))

        # Determine potential transpiration rate (no water stress)
        TrPot_NS = Kcb_NS * (NewCond.CCadj_NS) * Et0

        # Correct potential transpiration for dying green canopy effects
        if NewCond.CC_NS < NewCond.CCxW_NS:
            if (NewCond.CCxW_NS > 0.001) & (NewCond.CC_NS > 0.001):
                TrPot_NS = TrPot_NS * ((NewCond.CC_NS / NewCond.CCxW_NS) ** Crop.a_Tr)

        # 2. Potential prior water stress &/or delayed development
        # Update ageing days counter
        DAPadj = NewCond.DAP - NewCond.DelayedCDs
        if DAPadj > Crop.MaxCanopyCD:
            NewCond.AgeDays = DAPadj - Crop.MaxCanopyCD

        # Update crop coefficient for ageing of canopy
        if NewCond.AgeDays > 5:
            Kcb = Crop.Kcb - ((NewCond.AgeDays - 5) * (Crop.fage / 100)) * NewCond.CCxW
        else:
            Kcb = Crop.Kcb

        # Update crop coefficient for CO2 concentration
        if CO2CurrentConc > CO2RefConc:
            Kcb = Kcb * (1 - 0.05 * ((CO2CurrentConc - CO2RefConc) / (550 - CO2RefConc)))

        # Determine potential transpiration rate
        TrPot0 = Kcb * (NewCond.CCadj) * Et0
        # Correct potential transpiration for dying green canopy effects
        if NewCond.CC < NewCond.CCxW:
            if (NewCond.CCxW > 0.001) & (NewCond.CC > 0.001):
                TrPot0 = TrPot0 * ((NewCond.CC / NewCond.CCxW) ** Crop.a_Tr)

        # 3. Adjust potential transpiration for cold stress effects
        # Check if cold stress occurs on current day
        if Crop.TrColdStress == 0:
            # Cold temperature stress does not affect transpiration
            KsCold = 1
        elif Crop.TrColdStress == 1:
            # Transpiration can be affected by cold temperature stress
            if GDD >= Crop.GDD_up:
                # No cold temperature stress
                KsCold = 1
            elif GDD <= Crop.GDD_lo:
                # Transpiration fully inhibited by cold temperature stress
                KsCold = 0
            else:
                # Transpiration partially inhibited by cold temperature stress
                # Get parameters for logistic curve
                KsTr_up = 1
                KsTr_lo = 0.02
                fshapeb = (-1) * (
                    np.log(((KsTr_lo * KsTr_up) - 0.98 * KsTr_lo) / (0.98 * (KsTr_up - KsTr_lo)))
                )
                # Calculate cold stress level
                GDDrel = (GDD - Crop.GDD_lo) / (Crop.GDD_up - Crop.GDD_lo)
                KsCold = (KsTr_up * KsTr_lo) / (
                    KsTr_lo + (KsTr_up - KsTr_lo) * np.exp(-fshapeb * GDDrel)
                )
                KsCold = KsCold - KsTr_lo * (1 - GDDrel)

        # Correct potential transpiration rate (mm/day)
        TrPot0 = TrPot0 * KsCold
        TrPot_NS = TrPot_NS * KsCold

        # print(TrPot0,NewCond.DAP)

        ## Calculate surface layer transpiration ##
        if (NewCond.SurfaceStorage > 0) & (NewCond.DaySubmerged < Crop.LagAer):

            # Update submergence days counter
            NewCond.DaySubmerged = NewCond.DaySubmerged + 1
            # Update anerobic conditions counter for each compartment
            for ii in range(int(Soil_nComp)):
                # Increment aeration days counter for compartment ii
                NewCond.AerDaysComp[ii] = NewCond.AerDaysComp[ii] + 1
                if NewCond.AerDaysComp[ii] > Crop.LagAer:
                    NewCond.AerDaysComp[ii] = Crop.LagAer

            # Reduce actual transpiration that is possible to account for
            # aeration stress due to extended submergence
            fSub = 1 - (NewCond.DaySubmerged / Crop.LagAer)
            if NewCond.SurfaceStorage > (fSub * TrPot0):
                # Transpiration occurs from surface storage
                NewCond.SurfaceStorage = NewCond.SurfaceStorage - (fSub * TrPot0)
                TrAct0 = fSub * TrPot0
            else:
                # No transpiration from surface storage
                TrAct0 = 0

            if TrAct0 < (fSub * TrPot0):
                # More water can be extracted from soil profile for transpiration
                TrPot = (fSub * TrPot0) - TrAct0
                # print('now')

            else:
                # No more transpiration possible on current day
                TrPot = 0
                # print('here')

        else:

            # No surface transpiration occurs
            TrPot = TrPot0
            TrAct0 = 0

        # print(TrPot,NewCond.DAP)

        ## Update potential root zone transpiration for water stress ##
        # Determine root zone & top soil depletion, & root zone water
        # content
        _, Dr, TAW, thRZ = root_zone_water(
            Soil_Profile, float(NewCond.Zroot), NewCond.th, Soil_zTop, float(Crop.Zmin), Crop.Aer
        )
        # Check whether to use root zone or top soil depletions for calculating
        # water stress
        if (Dr.Rz / TAW.Rz) <= (Dr.Zt / TAW.Zt):
            # Root zone is wetter than top soil, so use root zone value
            Dr = Dr.Rz
            TAW = TAW.Rz
        else:
            # Top soil is wetter than root zone, so use top soil values
            Dr = Dr.Zt
            TAW = TAW.Zt

        # Calculate water stress coefficients
        beta = True
        Ksw = water_stress(Crop, NewCond, Dr, TAW, Et0, beta)

        # Calculate aeration stress coefficients
        Ksa_Aer, NewCond.AerDays = aeration_stress(NewCond.AerDays, Crop.LagAer, thRZ)
        # Maximum stress effect
        Ks = min(Ksw.StoLin, Ksa_Aer)
        # Update potential transpiration in root zone
        if IrrMngt_IrrMethod != 4:
            # No adjustment to TrPot for water stress when in net irrigation mode
            TrPot = TrPot * Ks

        ## Determine compartments covered by root zone ##
        # Compartments covered by the root zone
        rootdepth = round(max(float(NewCond.Zroot), float(Crop.Zmin)), 2)
        comp_sto = min(np.sum(Soil_Profile.dzsum < rootdepth) + 1, int(Soil_nComp))
        RootFact = np.zeros(int(Soil_nComp))
        # Determine fraction of each compartment covered by root zone
        for ii in range(comp_sto):
            if Soil_Profile.dzsum[ii] > rootdepth:
                RootFact[ii] = 1 - ((Soil_Profile.dzsum[ii] - rootdepth) / Soil_Profile.dz[ii])
            else:
                RootFact[ii] = 1

        ## Determine maximum sink term for each compartment ##
        SxComp = np.zeros(int(Soil_nComp))
        if IrrMngt_IrrMethod == 4:
            # Net irrigation mode
            for ii in range(comp_sto):
                SxComp[ii] = (Crop.SxTop + Crop.SxBot) / 2

        else:
            # Maximum sink term declines linearly with depth
            SxCompBot = Crop.SxTop
            for ii in range(comp_sto):
                SxCompTop = SxCompBot
                if Soil_Profile.dzsum[ii] <= rootdepth:
                    SxCompBot = Crop.SxBot * NewCond.rCor + (
                        (Crop.SxTop - Crop.SxBot * NewCond.rCor)
                        * ((rootdepth - Soil_Profile.dzsum[ii]) / rootdepth)
                    )
                else:
                    SxCompBot = Crop.SxBot * NewCond.rCor

                SxComp[ii] = (SxCompTop + SxCompBot) / 2

        # print(TrPot,NewCond.DAP)
        ## Extract water ##
        ToExtract = TrPot
        comp = -1
        TrAct = 0
        while (ToExtract > 0) & (comp < comp_sto - 1):
            # Increment compartment
            comp = comp + 1
            # Specify layer number

            # Determine TAW (m3/m3) for compartment
            thTAW = prof.th_fc[comp] - prof.th_wp[comp]
            if Crop.ETadj == 1:
                # Adjust stomatal stress threshold for Et0 on current day
                p_up_sto = Crop.p_up[1] + (0.04 * (5 - Et0)) * (np.log10(10 - 9 * Crop.p_up[1]))

            # Determine critical water content at which stomatal closure will
            # occur in compartment
            thCrit = prof.th_fc[comp] - (thTAW * p_up_sto)

            # Check for soil water stress
            if NewCond.th[comp] >= thCrit:
                # No water stress effects on transpiration
                KsComp = 1
            elif NewCond.th[comp] > prof.th_wp[comp]:
                # Transpiration from compartment is affected by water stress
                Wrel = (prof.th_fc[comp] - NewCond.th[comp]) / (prof.th_fc[comp] - prof.th_wp[comp])
                pRel = (Wrel - Crop.p_up[1]) / (Crop.p_lo[1] - Crop.p_up[1])
                if pRel <= 0:
                    KsComp = 1
                elif pRel >= 1:
                    KsComp = 0
                else:
                    KsComp = 1 - (
                        (np.exp(pRel * Crop.fshape_w[1]) - 1) / (np.exp(Crop.fshape_w[1]) - 1)
                    )

                if KsComp > 1:
                    KsComp = 1
                elif KsComp < 0:
                    KsComp = 0

            else:
                # No transpiration is possible from compartment as water
                # content does not exceed wilting point
                KsComp = 0

            # Adjust compartment stress factor for aeration stress
            if NewCond.DaySubmerged >= Crop.LagAer:
                # Full aeration stress - no transpiration possible from
                # compartment
                AerComp = 0
            elif NewCond.th[comp] > (prof.th_s[comp] - (Crop.Aer / 100)):
                # Increment aeration stress days counter
                NewCond.AerDaysComp[comp] = NewCond.AerDaysComp[comp] + 1
                if NewCond.AerDaysComp[comp] >= Crop.LagAer:
                    NewCond.AerDaysComp[comp] = Crop.LagAer
                    fAer = 0
                else:
                    fAer = 1

                # Calculate aeration stress factor
                AerComp = (prof.th_s[comp] - NewCond.th[comp]) / (
                    prof.th_s[comp] - (prof.th_s[comp] - (Crop.Aer / 100))
                )
                if AerComp < 0:
                    AerComp = 0

                AerComp = (fAer + (NewCond.AerDaysComp[comp] - 1) * AerComp) / (
                    fAer + NewCond.AerDaysComp[comp] - 1
                )
            else:
                # No aeration stress as number of submerged days does not
                # exceed threshold for initiation of aeration stress
                AerComp = 1
                NewCond.AerDaysComp[comp] = 0

            # Extract water
            ThToExtract = (ToExtract / 1000) / Soil_Profile.dz[comp]
            if IrrMngt_IrrMethod == 4:
                # Don't reduce compartment sink for stomatal water stress if in
                # net irrigation mode. Stress only occurs due to deficient
                # aeration conditions
                Sink = AerComp * SxComp[comp] * RootFact[comp]
            else:
                # Reduce compartment sink for greatest of stomatal & aeration
                # stress
                if KsComp == AerComp:
                    Sink = KsComp * SxComp[comp] * RootFact[comp]
                else:
                    Sink = min(KsComp, AerComp) * SxComp[comp] * RootFact[comp]

            # Limit extraction to demand
            if ThToExtract < Sink:
                Sink = ThToExtract

            # Limit extraction to avoid compartment water content dropping
            # below air dry
            if (InitCond_th[comp] - Sink) < prof.th_dry[comp]:
                Sink = InitCond_th[comp] - prof.th_dry[comp]
                if Sink < 0:
                    Sink = 0

            # Update water content in compartment
            NewCond.th[comp] = InitCond_th[comp] - Sink
            # Update amount of water to extract
            ToExtract = ToExtract - (Sink * 1000 * prof.dz[comp])
            # Update actual transpiration
            TrAct = TrAct + (Sink * 1000 * prof.dz[comp])

        ## Add net irrigation water requirement (if this mode is specified) ##
        if (IrrMngt_IrrMethod == 4) & (TrPot > 0):
            # Initialise net irrigation counter
            IrrNet = 0
            # Get root zone water content
            _, _Dr, _TAW, thRZ = root_zone_water(
                Soil_Profile,
                float(NewCond.Zroot),
                NewCond.th,
                Soil_zTop,
                float(Crop.Zmin),
                Crop.Aer,
            )
            NewCond.Depletion = _Dr.Rz
            NewCond.TAW = _TAW.Rz
            # Determine critical water content for net irrigation
            thCrit = thRZ.WP + ((IrrMngt_NetIrrSMT / 100) * (thRZ.FC - thRZ.WP))
            # Check if root zone water content is below net irrigation trigger
            if thRZ.Act < thCrit:
                # Initialise layer counter
                prelayer = 0
                for ii in range(comp_sto):
                    # Get soil layer
                    layeri = Soil_Profile.Layer[ii]
                    if layeri > prelayer:
                        # If in new layer, update critical water content for
                        # net irrigation
                        thCrit = prof.th_wp[ii] + (
                            (IrrMngt_NetIrrSMT / 100) * (prof.th_fc[ii] - prof.th_wp[ii])
                        )
                        # Update layer counter
                        prelayer = layeri

                    # Determine necessary change in water content in
                    # compartments to reach critical water content
                    dWC = RootFact[ii] * (thCrit - NewCond.th[ii]) * 1000 * prof.dz[ii]
                    # Update water content
                    NewCond.th[ii] = NewCond.th[ii] + (dWC / (1000 * prof.dz[ii]))
                    # Update net irrigation counter
                    IrrNet = IrrNet + dWC

            # Update net irrigation counter for the growing season
            NewCond.IrrNetCum = NewCond.IrrNetCum + IrrNet
        elif (IrrMngt_IrrMethod == 4) & (TrPot <= 0):
            # No net irrigation as potential transpiration is zero
            IrrNet = 0
        else:
            # No net irrigation as not in net irrigation mode
            IrrNet = 0
            NewCond.IrrNetCum = 0

        ## Add any surface transpiration to root zone total ##
        TrAct = TrAct + TrAct0

        ## Feedback with canopy cover development ##
        # If actual transpiration is zero then no canopy cover growth can occur
        if ((NewCond.CC - NewCond.CCprev) > 0.005) & (TrAct == 0):
            NewCond.CC = NewCond.CCprev

        ## Update transpiration ratio ##
        if TrPot0 > 0:
            if TrAct < TrPot0:
                NewCond.TrRatio = TrAct / TrPot0
            else:
                NewCond.TrRatio = 1

        else:
            NewCond.TrRatio = 1

        if NewCond.TrRatio < 0:
            NewCond.TrRatio = 0
        elif NewCond.TrRatio > 1:
            NewCond.TrRatio = 1

    else:
        # No transpiration if not in growing season
        TrAct = 0
        TrPot0 = 0
        TrPot_NS = 0
        # No irrigation if not in growing season
        IrrNet = 0
        NewCond.IrrNetCum = 0

    ## Store potential transpiration for irrigation calculations on next day ##
    NewCond.Tpot = TrPot0

    return TrAct, TrPot_NS, TrPot0, NewCond, IrrNet


# Cell
@njit()
def groundwater_inflow(prof, NewCond):
    """
    Function to calculate capillary rise in the presence of a shallow groundwater table

    <a href="../pdfs/ac_ref_man_3.pdf#page=61" target="_blank">Reference Manual: capillary rise calculations</a> (pg. 52-61)


    *Arguments:*



    `Soil`: `SoilClass` : Soil object containing soil paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters

    `GwIn`: `float` : Groundwater inflow


    """

    ## Store initial conditions for updating ##
    GwIn = 0

    ## Perform calculations ##
    if NewCond.WTinSoil == True:
        # Water table in soil profile. Calculate horizontal inflow.
        # Get groundwater table elevation on current day
        zGW = NewCond.zGW

        # Find compartment mid-points
        zMid = prof.zMid
        # For compartments below water table, set to saturation #
        idx = np.argwhere(zMid >= zGW).flatten()[0]
        for ii in range(idx, len(prof.Comp)):
            # Get soil layer
            if NewCond.th[ii] < prof.th_s[ii]:
                # Update water content
                dth = prof.th_s[ii] - NewCond.th[ii]
                NewCond.th[ii] = prof.th_s[ii]
                # Update groundwater inflow
                GwIn = GwIn + (dth * 1000 * prof.dz[ii])

    return NewCond, GwIn


# Cell
@njit()
def HIref_current_day(InitCond, Crop, GrowingSeason):
    """
    Function to calculate reference (no adjustment for stress effects)
    harvest index on current day

    <a href="../pdfs/ac_ref_man_3.pdf#page=119" target="_blank">Reference Manual: harvest index calculations</a> (pg. 110-126)



    *Arguments:*



    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `GrowingSeason`: `bool` : is growing season (True or Flase)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters




    """

    ## Store initial conditions for updating ##
    NewCond = InitCond

    InitCond_HIref = InitCond.HIref

    # NewCond.HIref = 0.

    ## Calculate reference harvest index (if in growing season) ##
    if GrowingSeason == True:
        # Check if in yield formation period
        tAdj = NewCond.DAP - NewCond.DelayedCDs
        if tAdj > Crop.HIstartCD:

            NewCond.YieldForm = True
        else:
            NewCond.YieldForm = False

        # Get time for harvest index calculation
        HIt = NewCond.DAP - NewCond.DelayedCDs - Crop.HIstartCD - 1

        if HIt <= 0:
            # Yet to reach time for HI build-up
            NewCond.HIref = 0
            NewCond.PctLagPhase = 0
        else:
            if NewCond.CCprev <= (Crop.CCmin * Crop.CCx):
                # HI cannot develop further as canopy cover is too small
                NewCond.HIref = InitCond_HIref
            else:
                # Check crop type
                if (Crop.CropType == 1) or (Crop.CropType == 2):
                    # If crop type is leafy vegetable or root/tuber, then proceed with
                    # logistic growth (i.e. no linear switch)
                    NewCond.PctLagPhase = 100  # No lag phase
                    # Calculate reference harvest index for current day
                    NewCond.HIref = (Crop.HIini * Crop.HI0) / (
                        Crop.HIini + (Crop.HI0 - Crop.HIini) * np.exp(-Crop.HIGC * HIt)
                    )
                    # Harvest index apprAOSP_hing maximum limit
                    if NewCond.HIref >= (0.9799 * Crop.HI0):
                        NewCond.HIref = Crop.HI0

                elif Crop.CropType == 3:
                    # If crop type is fruit/grain producing, check for linear switch
                    if HIt < Crop.tLinSwitch:
                        # Not yet reached linear switch point, therefore proceed with
                        # logistic build-up
                        NewCond.PctLagPhase = 100 * (HIt / Crop.tLinSwitch)
                        # Calculate reference harvest index for current day
                        # (logistic build-up)
                        NewCond.HIref = (Crop.HIini * Crop.HI0) / (
                            Crop.HIini + (Crop.HI0 - Crop.HIini) * np.exp(-Crop.HIGC * HIt)
                        )
                    else:
                        # Linear switch point has been reached
                        NewCond.PctLagPhase = 100
                        # Calculate reference harvest index for current day
                        # (logistic portion)
                        NewCond.HIref = (Crop.HIini * Crop.HI0) / (
                            Crop.HIini
                            + (Crop.HI0 - Crop.HIini) * np.exp(-Crop.HIGC * Crop.tLinSwitch)
                        )
                        # Calculate reference harvest index for current day
                        # (total - logistic portion + linear portion)
                        NewCond.HIref = NewCond.HIref + (Crop.dHILinear * (HIt - Crop.tLinSwitch))

                # Limit HIref & round off computed value
                if NewCond.HIref > Crop.HI0:
                    NewCond.HIref = Crop.HI0
                elif NewCond.HIref <= (Crop.HIini + 0.004):
                    NewCond.HIref = 0
                elif (Crop.HI0 - NewCond.HIref) < 0.004:
                    NewCond.HIref = Crop.HI0

    else:
        # Reference harvest index is zero outside of growing season
        NewCond.HIref = 0

    return NewCond


# Cell
@njit()
def biomass_accumulation(Crop, InitCond, Tr, TrPot, Et0, GrowingSeason):
    """
    Function to calculate biomass accumulation

    <a href="../pdfs/ac_ref_man_3.pdf#page=107" target="_blank">Reference Manual: biomass accumulaiton</a> (pg. 98-108)


    *Arguments:*



    `Crop`: `CropClass` : Crop object

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Tr`: `float` : Daily transpiration

    `TrPot`: `float` : Daily potential transpiration

    `Et0`: `float` : Daily reference evapotranspiration

    `GrowingSeason`:: `bool` : is Growing season? (True, False)

    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters




    """

    ## Store initial conditions in a new structure for updating ##
    NewCond = InitCond

    ## Calculate biomass accumulation (if in growing season) ##
    if GrowingSeason == True:
        # Get time for harvest index build-up
        HIt = NewCond.DAP - NewCond.DelayedCDs - Crop.HIstartCD - 1

        if ((Crop.CropType == 2) or (Crop.CropType == 3)) & (NewCond.HIref > 0):
            # Adjust WP for reproductive stage
            if Crop.Determinant == 1:
                fswitch = NewCond.PctLagPhase / 100
            else:
                if HIt < (Crop.YldFormCD / 3):
                    fswitch = HIt / (Crop.YldFormCD / 3)
                else:
                    fswitch = 1

            WPadj = Crop.WP * (1 - (1 - Crop.WPy / 100) * fswitch)
        else:
            WPadj = Crop.WP

        # print(WPadj)

        # Adjust WP for CO2 effects
        WPadj = WPadj * Crop.fCO2

        # print(WPadj)

        # Calculate biomass accumulation on current day
        # No water stress
        dB_NS = WPadj * (TrPot / Et0)
        # With water stress
        dB = WPadj * (Tr / Et0)
        if np.isnan(dB) == True:
            dB = 0

        # Update biomass accumulation
        NewCond.B = NewCond.B + dB
        NewCond.B_NS = NewCond.B_NS + dB_NS
    else:
        # No biomass accumulation outside of growing season
        NewCond.B = 0
        NewCond.B_NS = 0

    return NewCond


# Cell
@njit()
def temperature_stress(Crop, Tmax, Tmin):
    # Function to calculate temperature stress coefficients
    """
    Function to get irrigation depth for current day

    <a href="../pdfs/ac_ref_man_3.pdf#page=23" target="_blank">Reference Manual: temperature stress</a> (pg. 14)



    *Arguments:*



    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `Tmax`: `float` : max tempatature on current day (celcius)

    `Tmin`: `float` : min tempature on current day (celcius)


    *Returns:*


    `Kst`: `KstClass` : Kst object containing tempature stress paramators







    """

    ## Calculate temperature stress coefficients affecting crop pollination ##
    # Get parameters for logistic curve
    KsPol_up = 1
    KsPol_lo = 0.001

    Kst = KstClass()

    # Calculate effects of heat stress on pollination
    if Crop.PolHeatStress == 0:
        # No heat stress effects on pollination
        Kst.PolH = 1
    elif Crop.PolHeatStress == 1:
        # Pollination affected by heat stress
        if Tmax <= Crop.Tmax_lo:
            Kst.PolH = 1
        elif Tmax >= Crop.Tmax_up:
            Kst.PolH = 0
        else:
            Trel = (Tmax - Crop.Tmax_lo) / (Crop.Tmax_up - Crop.Tmax_lo)
            Kst.PolH = (KsPol_up * KsPol_lo) / (
                KsPol_lo + (KsPol_up - KsPol_lo) * np.exp(-Crop.fshape_b * (1 - Trel))
            )

    # Calculate effects of cold stress on pollination
    if Crop.PolColdStress == 0:
        # No cold stress effects on pollination
        Kst.PolC = 1
    elif Crop.PolColdStress == 1:
        # Pollination affected by cold stress
        if Tmin >= Crop.Tmin_up:
            Kst.PolC = 1
        elif Tmin <= Crop.Tmin_lo:
            Kst.PolC = 0
        else:
            Trel = (Crop.Tmin_up - Tmin) / (Crop.Tmin_up - Crop.Tmin_lo)
            Kst.PolC = (KsPol_up * KsPol_lo) / (
                KsPol_lo + (KsPol_up - KsPol_lo) * np.exp(-Crop.fshape_b * (1 - Trel))
            )

    return Kst


# Cell
@njit()
def HIadj_pre_anthesis(InitCond, Crop_dHI_pre):
    """
    Function to calculate adjustment to harvest index for pre-anthesis water
    stress

    <a href="../pdfs/ac_ref_man_3.pdf#page=119" target="_blank">Reference Manual: harvest index calculations</a> (pg. 110-126)


    *Arguments:*



    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Crop`: `CropClass` : Crop object containing Crop paramaters


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters


    """

    ## Store initial conditions in structure for updating ##
    NewCond = InitCond

    # check that there is an adjustment to be made
    if Crop_dHI_pre > 0:
        ## Calculate adjustment ##
        # Get parameters
        Br = InitCond.B / InitCond.B_NS
        Br_range = np.log(Crop_dHI_pre) / 5.62
        Br_upp = 1
        Br_low = 1 - Br_range
        Br_top = Br_upp - (Br_range / 3)

        # Get biomass ratios
        ratio_low = (Br - Br_low) / (Br_top - Br_low)
        ratio_upp = (Br - Br_top) / (Br_upp - Br_top)

        # Calculate adjustment factor
        if (Br >= Br_low) & (Br < Br_top):
            NewCond.Fpre = 1 + (
                ((1 + np.sin((1.5 - ratio_low) * np.pi)) / 2) * (Crop_dHI_pre / 100)
            )
        elif (Br > Br_top) & (Br <= Br_upp):
            NewCond.Fpre = 1 + (
                ((1 + np.sin((0.5 + ratio_upp) * np.pi)) / 2) * (Crop_dHI_pre / 100)
            )
        else:
            NewCond.Fpre = 1
    else:
        NewCond.Fpre = 1

    if NewCond.CC <= 0.01:
        # No green canopy cover left at start of flowering so no harvestable
        # crop will develop
        NewCond.Fpre = 0

    return NewCond


# Cell
@njit()
def HIadj_pollination(
    InitCond_CC, InitCond_Fpol, Crop_FloweringCD, Crop_CCmin, Crop_exc, Ksw, Kst, HIt
):
    """
    Function to calculate adjustment to harvest index for failure of
    pollination due to water or temperature stress

    <a href="../pdfs/ac_ref_man_3.pdf#page=119" target="_blank">Reference Manual: harvest index calculations</a> (pg. 110-126)


    *Arguments:*



    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `Ksw`: `KswClass` : Ksw object containing water stress paramaters

    `Kst`: `KstClass` : Kst object containing tempature stress paramaters

    `HIt`: `float` : time for harvest index build-up (calander days)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters



    """

    ## Caclulate harvest index adjustment for pollination ##
    # Get fractional flowering
    if HIt == 0:
        # No flowering yet
        FracFlow = 0
    elif HIt > 0:
        # Fractional flowering on previous day
        t1 = HIt - 1
        if t1 == 0:
            F1 = 0
        else:
            t1Pct = 100 * (t1 / Crop_FloweringCD)
            if t1Pct > 100:
                t1Pct = 100

            F1 = 0.00558 * np.exp(0.63 * np.log(t1Pct)) - (0.000969 * t1Pct) - 0.00383

        if F1 < 0:
            F1 = 0

        # Fractional flowering on current day
        t2 = HIt
        if t2 == 0:
            F2 = 0
        else:
            t2Pct = 100 * (t2 / Crop_FloweringCD)
            if t2Pct > 100:
                t2Pct = 100

            F2 = 0.00558 * np.exp(0.63 * np.log(t2Pct)) - (0.000969 * t2Pct) - 0.00383

        if F2 < 0:
            F2 = 0

        # Weight values
        if abs(F1 - F2) < 0.0000001:
            F = 0
        else:
            F = 100 * ((F1 + F2) / 2) / Crop_FloweringCD

        FracFlow = F

    # Calculate pollination adjustment for current day
    if InitCond_CC < Crop_CCmin:
        # No pollination can occur as canopy cover is smaller than minimum
        # threshold
        dFpol = 0
    else:
        Ks = min([Ksw.Pol, Kst.PolC, Kst.PolH])
        dFpol = Ks * FracFlow * (1 + (Crop_exc / 100))

    # Calculate pollination adjustment to date
    NewCond_Fpol = InitCond_Fpol + dFpol
    if NewCond_Fpol > 1:
        # Crop has fully pollinated
        NewCond_Fpol = 1

    return NewCond_Fpol


# Cell
@njit()
def HIadj_post_anthesis(InitCond, Crop, Ksw):
    """
    Function to calculate adjustment to harvest index for post-anthesis water
    stress

    <a href="../pdfs/ac_ref_man_3.pdf#page=119" target="_blank">Reference Manual: harvest index calculations</a> (pg. 110-126)


    *Arguments:*



    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `Ksw`: `KswClass` : Ksw object containing water stress paramaters

    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters


    """

    ## Store initial conditions in a structure for updating ##
    NewCond = InitCond

    InitCond_DelayedCDs = InitCond.DelayedCDs
    InitCond_sCor1 = InitCond.sCor1
    InitCond_sCor2 = InitCond.sCor2

    ## Calculate harvest index adjustment ##
    # 1. Adjustment for leaf expansion
    tmax1 = Crop.CanopyDevEndCD - Crop.HIstartCD
    DAP = NewCond.DAP - InitCond_DelayedCDs
    if (
        (DAP <= (Crop.CanopyDevEndCD + 1))
        & (tmax1 > 0)
        & (NewCond.Fpre > 0.99)
        & (NewCond.CC > 0.001)
        & (Crop.a_HI > 0)
    ):
        dCor = 1 + (1 - Ksw.Exp) / Crop.a_HI
        NewCond.sCor1 = InitCond_sCor1 + (dCor / tmax1)
        DayCor = DAP - 1 - Crop.HIstartCD
        NewCond.fpost_upp = (tmax1 / DayCor) * NewCond.sCor1

    # 2. Adjustment for stomatal closure
    tmax2 = Crop.YldFormCD
    DAP = NewCond.DAP - InitCond_DelayedCDs
    if (
        (DAP <= (Crop.HIendCD + 1))
        & (tmax2 > 0)
        & (NewCond.Fpre > 0.99)
        & (NewCond.CC > 0.001)
        & (Crop.b_HI > 0)
    ):
        # print(Ksw.Sto)
        dCor = np.power(Ksw.Sto, 0.1) * (1 - (1 - Ksw.Sto) / Crop.b_HI)
        NewCond.sCor2 = InitCond_sCor2 + (dCor / tmax2)
        DayCor = DAP - 1 - Crop.HIstartCD
        NewCond.fpost_dwn = (tmax2 / DayCor) * NewCond.sCor2

    # Determine total multiplier
    if (tmax1 == 0) & (tmax2 == 0):
        NewCond.Fpost = 1
    else:
        if tmax2 == 0:
            NewCond.Fpost = NewCond.fpost_upp
        else:
            if tmax1 == 0:
                NewCond.Fpost = NewCond.fpost_dwn
            elif tmax1 <= tmax2:
                NewCond.Fpost = NewCond.fpost_dwn * (
                    ((tmax1 * NewCond.fpost_upp) + (tmax2 - tmax1)) / tmax2
                )
            else:
                NewCond.Fpost = NewCond.fpost_upp * (
                    ((tmax2 * NewCond.fpost_dwn) + (tmax1 - tmax2)) / tmax1
                )

    return NewCond


# Cell
@njit()
def harvest_index(Soil_Profile, Soil_zTop, Crop, InitCond, Et0, Tmax, Tmin, GrowingSeason):

    """
    Function to simulate build up of harvest index


     <a href="../pdfs/ac_ref_man_3.pdf#page=119" target="_blank">Reference Manual: harvest index calculations</a> (pg. 110-126)

    *Arguments:*


    `Soil`: `SoilClass` : Soil object containing soil paramaters

    `Crop`: `CropClass` : Crop object containing Crop paramaters

    `InitCond`: `InitCondClass` : InitCond object containing model paramaters

    `Et0`: `float` : reference evapotranspiration on current day

    `Tmax`: `float` : maximum tempature on current day (celcius)

    `Tmin`: `float` : minimum tempature on current day (celcius)

    `GrowingSeason`:: `bool` : is growing season (True or Flase)


    *Returns:*


    `NewCond`: `InitCondClass` : InitCond object containing updated model paramaters



    """

    ## Store initial conditions for updating ##
    NewCond = InitCond

    InitCond_HI = InitCond.HI
    InitCond_HIadj = InitCond.HIadj
    InitCond_PreAdj = InitCond.PreAdj

    ## Calculate harvest index build up (if in growing season) ##
    if GrowingSeason == True:
        # Calculate root zone water content
        _, Dr, TAW, _ = root_zone_water(
            Soil_Profile, float(NewCond.Zroot), NewCond.th, Soil_zTop, float(Crop.Zmin), Crop.Aer
        )
        # Check whether to use root zone or top soil depletions for calculating
        # water stress
        if (Dr.Rz / TAW.Rz) <= (Dr.Zt / TAW.Zt):
            # Root zone is wetter than top soil, so use root zone value
            Dr = Dr.Rz
            TAW = TAW.Rz
        else:
            # Top soil is wetter than root zone, so use top soil values
            Dr = Dr.Zt
            TAW = TAW.Zt

        # Calculate water stress
        beta = True
        Ksw = water_stress(Crop, NewCond, Dr, TAW, Et0, beta)

        # Calculate temperature stress
        Kst = temperature_stress(Crop, Tmax, Tmin)

        # Get reference harvest index on current day
        HIi = NewCond.HIref

        # Get time for harvest index build-up
        HIt = NewCond.DAP - NewCond.DelayedCDs - Crop.HIstartCD - 1

        # Calculate harvest index
        if (NewCond.YieldForm == True) & (HIt >= 0):
            # print(NewCond.DAP)
            # Root/tuber or fruit/grain crops
            if (Crop.CropType == 2) or (Crop.CropType == 3):
                # Detemine adjustment for water stress before anthesis
                if InitCond_PreAdj == False:
                    InitCond.PreAdj = True
                    NewCond = HIadj_pre_anthesis(NewCond, Crop.dHI_pre)

                # Determine adjustment for crop pollination failure
                if Crop.CropType == 3:  # Adjustment only for fruit/grain crops
                    if (HIt > 0) & (HIt <= Crop.FloweringCD):

                        NewCond.Fpol = HIadj_pollination(
                            InitCond.CC,
                            InitCond.Fpol,
                            Crop.FloweringCD,
                            Crop.CCmin,
                            Crop.exc,
                            Ksw,
                            Kst,
                            HIt,
                        )

                    HImax = NewCond.Fpol * Crop.HI0
                else:
                    # No pollination adjustment for root/tuber crops
                    HImax = Crop.HI0

                # Determine adjustments for post-anthesis water stress
                if HIt > 0:
                    NewCond = HIadj_post_anthesis(NewCond, Crop, Ksw)

                # Limit HI to maximum allowable increase due to pre- &
                # post-anthesis water stress combinations
                HImult = NewCond.Fpre * NewCond.Fpost
                if HImult > 1 + (Crop.dHI0 / 100):
                    HImult = 1 + (Crop.dHI0 / 100)

                # Determine harvest index on current day, adjusted for stress
                # effects
                if HImax >= HIi:
                    HIadj = HImult * HIi
                else:
                    HIadj = HImult * HImax

            elif Crop.CropType == 1:
                # Leafy vegetable crops - no adjustment, harvest index equal to
                # reference value for current day
                HIadj = HIi

        else:

            # No build-up of harvest index if outside yield formation period
            HIi = InitCond_HI
            HIadj = InitCond_HIadj

        # Store final values for current time step
        NewCond.HI = HIi
        NewCond.HIadj = HIadj

    else:
        # No harvestable crop outside of a growing season
        NewCond.HI = 0
        NewCond.HIadj = 0

    # print([NewCond.DAP , Crop.YldFormCD])
    return NewCond