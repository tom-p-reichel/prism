"""
Miscellaneous console-related utilities.
"""
import resource
import signal
import warnings
from enum import IntEnum
from typing import Callable, Dict, Optional, Tuple, TypedDict, Union


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
    Create function to raise `exception` when called.

    The fuction return is intended to passed to `signal.signal`.
    https://docs.python.org/3.8/library/signal.html#signal.signal
    """

    def signal_handler(signo, frame):
        raise exception

    return signal_handler


ResourceLimits = Union[int, Tuple[int, int]]
"""
A max size for a resource.

If an int is given, it is assumed to be a soft limit. If a
2-tuple of ints are given, the 0 index is taken to be a soft
limit and 1 index is taken to be the hard limit.
"""


def split_limit(
        limit: Optional[ResourceLimits]) -> Tuple[Optional[int],
                                                  Optional[int]]:
    """
    Determine soft and hard limit from a ResourceLimit.

    Parameters
    ----------
    limit : Optional[ResourceLimits]
        A resource limit, or None.

    Returns
    -------
    Tuple[Optional[int], Optional[int]]
        Tuple containing soft and hard limit.
    """
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
    return soft, hard


class ResourceMapValueDict(TypedDict):
    """
    Dictionary of keywords used to set resource limits.
    """

    exception: Optional[Exception]
    """
    Exception raised when resource soft limit is passed.
    If None, then the default exception for that resource
    is used.
    """
    soft: Optional[int]
    """
    Soft resource limit. Does not result in SIGKILL signal
    when passed. Specific signal depends on resource.
    By default, None.
    """
    hard: Optional[int]
    """
    Hard resource limit. Results in SIGKILL signal
    when passed. By default, None.
    """


def _value_to_valuedict(
        value: Union[ResourceLimits,
                     Exception]) -> ResourceMapValueDict:
    """
    Return a ResourceMapValueDict that contains the given value.

    Parameters
    ----------
    value : Union[ResourceLimits, Exception]
        Value to place in ResourceMapValueDict

    Returns
    -------
    ResourceMapValueDict
        Dictionary mapping the value data to
        specific keys in ResourceMapValueDict.
    """
    value_dict: ResourceMapValueDict = {}
    if isinstance(value, Exception):
        value_dict['exception'] = value
    else:
        soft, hard = split_limit(value)
        if soft is not None:
            value_dict['soft'] = soft
        if hard is not None:
            value_dict['hard'] = hard,
    return value_dict


def _repeated_valuedict_keys_msg(resource_name: str, key: str) -> str:
    """
    Return message for repeated values corresponding to same resource.

    Parameters
    ----------
    resource_name : str
        Resource name
    key : str
        A ResourceMapValueDict key.

    Returns
    -------
    str
        Messaging describing which resource name has repeated values.

    Raises
    ------
    ValueError
        Key is not a key expected by ResourceMapValueDict.
    """
    if key == "exception":
        name = "exception"
    elif key == "soft":
        name = "soft limit"
    elif key == "hard":
        name = "hard limit"
    else:
        raise ValueError(f"Unexpected key ('{key}') for ResourceMapValueDict")
    return f"Multiple {name}s given for {resource_name}"


class ProcessResource(IntEnum):
    """
    Enumeration of resources thatcan be limited.
    """

    MEMORY: int = resource.RLIMIT_AS
    """
    The maximum area (in bytes) of address space which may be taken
    by the process.
    """

    RUNTIME: int = resource.RLIMIT_CPU
    """
    The maximum amount of processor time (in seconds) that a
    process can use. If this limit is exceeded, a SIGXCPU signal
    is sent to the process.
    """

    def _limit_current_process(self, rss_map_value_dict: ResourceMapValueDict):
        """
        Limit the resource usage of the current process.

        Parameters
        ----------
        rss_map_value_dict: ResourceMapValueDict
            Dictionary containing soft limit, hard limit, and
            resource specific exception. See ResourceMapValueDict
            for details.

        Raises
        ------
        ValueError
            An exception was given when `self` was not
            `ProcessResource.RUNTIME`.
        """
        # Get existing limits
        existing = resource.getrlimit(self.value)
        # Get requested soft and hard limits
        soft = rss_map_value_dict.get('soft', None)
        hard = rss_map_value_dict.get('hard', None)
        # Get requested exception for when soft limit is passed.
        exception = rss_map_value_dict.get('exception', None)
        # Use existing limit when requested limit is None.
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
    def create_resource_map(
        cls,
        **kwargs: Dict[Union[str,
                             int,
                             'ProcessResource'],
                       Union[ResourceLimits,
                             Exception]]
    ) -> Dict['ProcessResource',
              ResourceMapValueDict]:
        """
        Create map between resources and limits/exception.

        Returns
        -------
        Dict['ProcessResource', ResourceMapValueDict]
            A mapping between a specific resource and the limits
            on that resource, as well as the exception raised
            when the soft resource limit is exceeded.

        Raises
        ------
        ValueError
            Multiple soft limits, hard limits, or exceptions
            were given for the same resource.
        """
        resource_map = {}
        for rss, value in set(kwargs.keys()):
            value_dict = _value_to_valuedict(value)

            # Convert resource to ProcessResource
            if isinstance(rss, str):
                rss = cls[rss]
            elif isinstance(rss, int):
                rss = cls(rss)

            # Add values to resource map
            if rss not in resource_map:
                resource_map[rss] = {}
            for k in value_dict:
                if k in resource_map[rss]:
                    raise ValueError(_repeated_valuedict_keys_msg(rss.name, k))
            resource_map[rss].update(value_dict)
        return resource_map

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
            If `limits` is None or empty dict, `cmd` is returned
            without modification. Otherwise the "timeout" bash command
            with corresponding flags and values are prepended to `cmd`
            and returned.
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
        """
        if limits is None:
            limits = {}
        if exceptions is None:
            exceptions = {}

        # Aggregate limits and exceptions into single dictionary that
        # uses `ProcessResource` as keys and keyword arguments of the
        # `ProcessRsource.<value>._limit_current_process` method as
        # values.
        resource_map = cls.create_resource_map(**limits)
        resource_map.update(cls.create_resource_map(**exceptions))

        # Apply resource constraints.
        for rss, rss_map_value_dict in resource_map.items():
            rss._limit_current_process(rss_map_value_dict)


def subprocess_resource_limiter(
    memory: Optional[ResourceLimits] = None,
    runtime: Optional[ResourceLimits] = None,
    max_runtime_exception: Exception = None,
) -> Callable[[],
              None]:
    """
    Return function limits resources that when called.

    Parameters
    ----------
    memory : Optional[int], optional
        Maximum memory allowed, by default None
    runtime : Optional[int], optional
        maximum time allowed, by default None
    max_time_exception : Exception, optional
        Exception that is raised when max runtime is exceeded,
        by default `None`. If `None` is given, then a MaxRuntimeError
        exception is used instead. See
        `ProcessResource.limit_current_process`.

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