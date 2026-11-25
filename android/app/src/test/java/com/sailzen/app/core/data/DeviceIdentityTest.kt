package com.sailzen.app.core.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DeviceIdentityTest {

    @Test
    fun buildStableIds_deterministicAcrossReinstalls() {
        val (id1, fp1) = DeviceIdentity.buildStableIds("a1b2c3d4e5f60708", "HONOR", "PNM-AN10")
        val (id2, fp2) = DeviceIdentity.buildStableIds("A1B2C3D4E5F60708", "honor", "pnm-an10")
        assertEquals(id1, id2)
        assertEquals(fp1, fp2)
        assertTrue(id1!!.startsWith("android-"))
        assertTrue(fp1.startsWith("android:"))

        val (otherId, otherFp) = DeviceIdentity.buildStableIds("ffeeddccbbaa9988", "HONOR", "PNM-AN10")
        assertNotEquals(id1, otherId)
        assertNotEquals(fp1, otherFp)
    }

    @Test
    fun buildStableIds_rejectsBlankOrKnownBadAndroidId() {
        val (id1, fp1) = DeviceIdentity.buildStableIds(null, "HONOR", "PNM-AN10")
        assertNull(id1)
        assertEquals("", fp1)

        val (id2, fp2) = DeviceIdentity.buildStableIds("9774d56d682e549c", "HONOR", "PNM-AN10")
        assertNull(id2)
        assertEquals("", fp2)
    }

    @Test
    fun formatDisplayName_avoidsDuplicateManufacturerPrefixAndLabelsEmulators() {
        assertEquals("HONOR PNM-AN10", DeviceIdentity.formatDisplayName("HONOR", "PNM-AN10", false))
        assertEquals("HONOR Magic6", DeviceIdentity.formatDisplayName("HONOR", "HONOR Magic6", false))
        assertEquals("模拟器 (sdk_gphone64_x86_64)", DeviceIdentity.formatDisplayName("Google", "sdk_gphone64_x86_64", true))
    }

    @Test
    fun detectEmulator_distinguishesRealDeviceFromEmulator() {
        assertTrue(
            DeviceIdentity.detectEmulator(
                fingerprint = "google/sdk_gphone64_x86_64/emu64xa:15",
                model = "sdk_gphone64_x86_64",
                hardware = "ranchu",
                product = "sdk_gphone64_x86_64",
                brand = "google",
            ),
        )
        assertFalse(
            DeviceIdentity.detectEmulator(
                fingerprint = "HONOR/PNM-AN10/HNPNM:15",
                model = "PNM-AN10",
                hardware = "qcom",
                product = "PNM-AN10",
                brand = "HONOR",
            ),
        )
    }
}
