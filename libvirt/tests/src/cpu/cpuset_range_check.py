import logging

from virttest import virsh
from virttest.libvirt_xml import vm_xml
from virttest.utils_test import libvirt


def run(test, params, env):
    """
    Test whether libvirt check the range of cpuset before starting vm

    1. virsh nodeinfo --> host cpu number
    2. change cpuset in xml to be out of the range of host cpu number
    3. start vm with illegal cpuset and failed
    4. start vm with legal cpuset and succeed
    5. virsh vcpuinfo to check cpu affinity
    """

    vm_name = params.get("main_vm")
    vm = env.get_vm(vm_name)
    cpuset_mask = params.get("cpuset_mask", "2")

    vmxml = vm_xml.VMXML.new_from_dumpxml(vm_name)
    vmxml_backup = vmxml.copy()

    try:
        # get host cpu number
        ret = virsh.nodeinfo(debug=True)
        output = ret.stdout.strip()
        for x in output.splitlines():
            if "CPU(s):" in x and len(x.split(':')) > 1:
                hostcpu_num = int(x.split(':')[1])
        if not hostcpu_num:
            test.fail("fail to get host cpu number")

        # change cpuset in xml to be out of the range of host cpu number
        cpuset_illegal = "0-{},^{}".format(hostcpu_num, cpuset_mask)
        vmxml.cpuset = cpuset_illegal
        logging.debug(vmxml)
        vmxml.sync()

        # start vm with illegal cpuset and failed
        ret = virsh.start(vm_name, debug=True, ignore_status=True)
        libvirt.check_result(ret, "Numerical result out of range")

        # start vm with legal cpuset in xml and succeed
        cpuset = "0-{},^{}".format(hostcpu_num-1, cpuset_mask)
        vmxml.cpuset = cpuset
        logging.debug(vmxml)
        vmxml.sync()
        vm.start()
        vm.wait_for_login().close()

        # check cpu affinity
        output = virsh.vcpuinfo(vm_name, debug=True).stdout.strip()
        for x in output.splitlines():
            if "CPU Affinity:" in x and len(x.split(':')) > 1:
                cpu_affinity = x.split(':')[1].strip()
                break

        if cpu_affinity[int(cpuset_mask)] != "-":
            test.fail("cpu affinity error")
    finally:
        vmxml_backup.sync()
