"""
Miscellaneous console-related utilities.
"""
import resource
import signal
import warnings
from enum import IntEnum
from typing import Callable, Dict, Optional, Tuple, Union


class MaxRuntimeError(RuntimeError):
    """
    Exception Raised when runtime is exceeded.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize exception.
        """
        super().__init__(*args, **kwargs)


def get_handler(exception: Exception):
    """
    Create handler function to raise exception.
    """

    def signal_handler(signo, frame):
        raise exception

    return signal_handler


ResourceLimits = Union[int, Tuple[int, int]]


class ProcessResource(IntEnum):
    """
    Enumeration of resources thatcan be limited.

    Attributes
    ----------
    MEMORY : int
        The maximum area (in bytes) of address space which may be taken
        by the process.
    RUNTIME : int
        The maximum amount of processor time (in seconds) that a
        process can use. If this limit is exceeded, a SIGXCPU signal
        is sent to the process.
    """

    MEMORY: int = resource.RLIMIT_AS
    RUNTIME: int = resource.RLIMIT_CPU

    def _limit_current_process(
            self,
            soft: Optional[int] = None,
            hard: Optional[int] = None,
            exception: Optional[Exception] = None):
        """
        Limit the resource usage of the current process.

        Parameters
        ----------
        exception : Optional[Exception], optional
            An exception to be raised by signal handler when soft
            limit is passed, by default None. Only supported for
            `ProcessResource.RUNTIME`. `ProcessResource.MEMORY`
            raises a `MemoryError` already.

        Raises
        ------
        ValueError
            An exception was given a value other than
            `ProcessResource.RUNTIME`.
        """
        # Get existing limits
        existing = resource.getrlimit(self.value)

        # Use existing limit when requested value is None.
        if soft is None and hard is not None:
            # Use existing soft limit and requested hard limit.
            soft = existing[0]
            if soft > hard:
                # Lower existing soft limit so that it's not larger
                # than requested hard limit.
                warnings.warn(
                    f"Lowering existing {self.name} soft limit ({soft})"
                    f" to match requested {self.name} hard limit ({hard}).")
                soft = hard
        elif hard is None and soft is not None:
            # Use existing hard limit and requested soft limit.
            hard = existing[1]

        # Only set limits if one or both limits are given.
        # If invalid pair is used, `setrlimit` will raise a
        # ValueError exception.
        if soft is not None and hard is not None:
            limits = (soft, hard)
            resource.setrlimit(self.value, limits)

        # Set handler for signal when limit is passed that
        # raises the given exception.
        if self == ProcessResource.RUNTIME:
            # Raised if soft limit is passed.
            signum = signal.SIGXCPU
            exception = exception or MaxRuntimeError(
                f"Max runtime exceeded: {soft}")
            # Get handler
            handler = get_handler(exception)
            # Set handler
            signal.signal(signum, handler)
        if self == ProcessResource.MEMORY and exception is not None:
            # Python already returns MemoryError.
            raise ValueError(
                "MemoryError is raised when memory limit is exceeded."
                " Cannot set custom exception for memory limits.")

    def _timeout_command_flag(self, limit: ResourceLimits) -> str:
        """
        Return flag and value corresponding to `timeout` shell command.

        Parameters
        ----------
        limit : int
            Maximum allowed resource usage.

        Returns
        -------
        str
            A string containing the flag used by `timeout`
            to limit the corresponding resource usage followed
            by the given `limit`.
        """
        if isinstance(limit, int):
            soft_limit = limit
        elif isinstance(limit, tuple):
            soft_limit, _ = limit

        if self.value == ProcessResource.RUNTIME:
            flag = f"-t {soft_limit}"
        elif self.value == ProcessResource.MEMORY:
            flag = f"-m {soft_limit}"
        return flag

    @classmethod
    def limit_command(
        cls,
        cmd: str,
        limits: Optional[Dict[Union[str,
                                    int,
                                    'ProcessResource'],
                              ResourceLimits]] = None
    ) -> str:
        """
        Return bash command run `cmd` with resource constraints.

        If `kwargs` is empty then `cmd` is returned.

        Parameters
        ----------
        cmd : str
            Command that will run with resource constraints.
        limits: Optional[Dict[Union[str, int, 'ProcessResource'],
                              ResourceLimits]], optional
            A dictionary mapping different ProcessResource
            enumeration names to maximum values.

        Returns
        -------
        str
            If `memory` and `runtime` are both `None`,
            then an empty string is returned. Otherwise,
            a string that can be prepended to an existing
            command string to limit the resources of that
            original command will be returned.
        """
        flags = []
        if limits is None:
            limits = {}
        for rss, limit in limits.items():
            if isinstance(rss, str):
                rss = ProcessResource[rss]
            elif isinstance(resource, int):
                rss = ProcessResource(rss)
            flag = rss._timeout_command_flag(limit)
            flags.append(flag)
        if len(flags) > 0:
            cmd = ' '.join(['timeout'] + flags + [cmd])
        return cmd

    @classmethod
    def limit_current_process(
        cls,
        limits: Optional[Dict[Union[str,
                                    int,
                                    'ProcessResource'],
                              ResourceLimits]] = None,
        exceptions: Optional[Dict[Union[str,
                                        int,
                                        'ProcessResource'],
                                  Exception]] = None):
        """
        Limit the resource usage of the current process.

        Parameters
        ----------
        limits: Optional[Dict[Union[str, int, 'ProcessResource'],
                         ResourceLimits]], optional
            A dictionary mapping different ProcessResource
            and a limit on that resource.
        exceptions : Optional[Dict[Union[str, int, 'ProcessResource'],
                              Exception]], optional
            A dictionary mapping different ProcessResource
            and exceptions to be raised when limit is exceeded.
            Current only supported for `ProcessResource.RUNTIME`.
            `ProcessResource.MEMORY` raises a `MemoryError` already.
            Keys in `exceptions` must keys

        Raises
        ------
        ValueError
            An exception was given a value other than
            `ProcessResource.RUNTIME`.
        """
        if limits is None:
            limits = {}
        if exceptions is None:
            exceptions = {}

        # Aggregate limits and exceptions into single dictionary that
        # uses `ProcessResource` as keys and keyword arguments of the
        # `ProcessRsource.<value>._limit_current_process` method as
        # values.
        resource_map = {}
        for rss in set(list(limits.keys()) + list(exceptions.keys())):
            exception = exceptions.get(rss, None)

            # Determine soft and hard limits from `limit`.
            limit = limits.get(rss, None)
            if limit is None:
                soft = None
                hard = None
            elif isinstance(limit, int):
                soft = limit
                hard = None
            elif len(limit) == 1:
                soft = limit[0]
                hard = None
            elif len(limit) == 2:
                soft = limit[0]
                hard = limit[1]

            # Convert resource to ProcessResource
            if isinstance(rss, str):
                rss = ProcessResource[rss]
            elif isinstance(rss, int):
                rss = ProcessResource(rss)

            # Add values to resource map
            if rss not in resource_map:
                resource_map[rss] = dict()
            if soft is not None:
                resource_map[rss]['soft'] = soft
            if hard is not None:
                resource_map[rss]['hard'] = hard
            if exception is not None:
                resource_map[rss]['exception'] = exception

        # Apply resource constraints.
        for rss, kwargs in resource_map.items():
            rss._limit_current_process(**kwargs)


def subprocess_resource_limiter(
    memory: Optional[int] = None,
    runtime: Optional[int] = None,
    max_runtime_exception: Exception = None,
) -> Callable[[],
              ]:
    """
    Return function limits resources that when called.

    Parameters
    ----------
    memory : Optional[int], optional
        Maximum memory allowed, by default None
    runtime : Optional[int], optional
        maximum time allowed, by default None
    max_time_exception : Exception, optional
        _description_, by default None
    Returns
    -------
    Callable
        Function that can be called in a subprocess to
        limit resources of that subprocess.
    """

    def limiter():
        limits = {
            ProcessResource.MEMORY: memory,
            ProcessResource.RUNTIME: runtime
        }
        exceptions = {
            ProcessResource.RUNTIME: max_runtime_exception,
        }
        ProcessResource.limit_current_process(limits, exceptions)

    return limiter
